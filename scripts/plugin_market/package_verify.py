from __future__ import annotations

import argparse
import json
import mimetypes
import os
import time
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from plugin_market.checksum_store import GitHubReleaseChecksumStore
from plugin_market.common import (
    PluginMarketError,
    download_file,
    ensure_directory,
    error,
    log,
    sha256_file,
    warn,
    write_github_output,
    write_json_file,
)
from plugin_market.manifest import parse_manifest_file, parse_manifest_text, validate_manifest


ZIP_MAGIC_HEADERS = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
DEFAULT_MAX_AUTOVERIFY_SIZE = int(os.environ.get("PLUGIN_MARKET_MAX_AUTOVERIFY_SIZE_BYTES", str(100 * 1024 * 1024)))
DEFAULT_SANDBOX_TIMEOUT = int(os.environ.get("PLUGIN_MARKET_SANDBOX_TIMEOUT_SECONDS", "600"))
DEFAULT_MIN_ENGINES = int(os.environ.get("PLUGIN_MARKET_MIN_ENGINES_FOR_PASS", "20"))
DEFAULT_SANDBOX_RUNTIME = int(os.environ.get("PLUGIN_MARKET_SANDBOX_RUNTIME_SECONDS", "280"))


@dataclass
class PackageMetadata:
    plugin_id: str
    manifest_path: str
    download_url: str
    package_path: Path
    sha256: str
    file_size_bytes: int
    file_size_mb: float


def validate_zip_package(path: Path) -> None:
    with path.open("rb") as handle:
        header = handle.read(4)
    if not any(header.startswith(prefix) for prefix in ZIP_MAGIC_HEADERS):
        raise PluginMarketError(f"{path.name} is not a valid ZIP package")

    try:
        with zipfile.ZipFile(path, "r") as archive:
            corrupt_member = archive.testzip()
            if corrupt_member is not None:
                raise PluginMarketError(f"ZIP archive is corrupt at member '{corrupt_member}'")
    except zipfile.BadZipFile as exc:
        raise PluginMarketError(f"{path.name} is not a readable ZIP archive") from exc


def validate_package_manifest_plugin_id(path: Path, expected_plugin_id: str) -> None:
    try:
        with zipfile.ZipFile(path, "r") as archive:
            manifest_candidates = [
                name
                for name in archive.namelist()
                if not name.endswith("/") and Path(name).name.lower() == "manifest.yml"
            ]
            if not manifest_candidates:
                raise PluginMarketError(f"{path.name} does not contain a package manifest.yml")
            if len(manifest_candidates) > 1:
                raise PluginMarketError(
                    f"{path.name} contains multiple manifest.yml files: {', '.join(manifest_candidates)}"
                )

            package_manifest_path = manifest_candidates[0]
            package_manifest_text = archive.read(package_manifest_path).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PluginMarketError(f"{path.name} package manifest.yml is not valid UTF-8") from exc

    package_manifest = parse_manifest_text(package_manifest_text, f"{path.name}:{package_manifest_path}")
    package_plugin_id = str(package_manifest.get("id", "")).strip()
    if not package_plugin_id:
        raise PluginMarketError(f"{path.name}:{package_manifest_path} is missing required field 'id'")
    if package_plugin_id != expected_plugin_id:
        raise PluginMarketError(
            f"Package manifest id '{package_plugin_id}' does not match plugin manifest id '{expected_plugin_id}'"
        )


def fetch_package(manifest_path: Path, download_dir: Path) -> PackageMetadata:
    manifest = parse_manifest_file(manifest_path)
    errors = validate_manifest(manifest, source=str(manifest_path), manifest_path=str(manifest_path))
    if errors:
        raise PluginMarketError("\n".join(errors))
    plugin_id = manifest["id"]
    if manifest_path.stem != plugin_id:
        raise PluginMarketError(
            f"Manifest file name '{manifest_path.name}' must match plugin id '{plugin_id}'"
        )
    download_url = manifest["downloadURL"]
    package_path = download_dir / f"{plugin_id}.zip"

    download_file(download_url, package_path)
    validate_zip_package(package_path)
    validate_package_manifest_plugin_id(package_path, plugin_id)

    file_size_bytes = package_path.stat().st_size
    sha256 = sha256_file(package_path)
    return PackageMetadata(
        plugin_id=plugin_id,
        manifest_path=str(manifest_path.relative_to(manifest_path.parents[1])),
        download_url=download_url,
        package_path=package_path,
        sha256=sha256,
        file_size_bytes=file_size_bytes,
        file_size_mb=round(file_size_bytes / (1024 * 1024), 2),
    )


def create_verified_result(
    *,
    metadata: PackageMetadata,
    head_sha: str,
    needs_manual_review: bool,
    output_path: Path,
) -> Path:
    payload = {
        "pluginId": metadata.plugin_id,
        "sha256": metadata.sha256,
        "headSha": head_sha,
        "downloadURL": metadata.download_url,
        "manifestPath": metadata.manifest_path,
        "needsManualReview": needs_manual_review,
    }
    write_json_file(output_path, payload)
    return output_path


def upload_to_threatbook(package_path: Path, api_key: str, runtime: int) -> dict[str, Any]:
    boundary = f"----PluginMarketBoundary{int(time.time() * 1000)}"
    file_name = package_path.name
    mime_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"

    parts: list[bytes] = []
    fields = {
        "apikey": api_key,
        "sandbox_type": "win10_1903_enx64_office2016",
        "runtime": str(runtime),
    }

    for key, value in fields.items():
        parts.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{key}"\r\n\r\n'
                f"{value}\r\n"
            ).encode("utf-8")
        )

    parts.append(
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{file_name}"\r\n'
            f"Content-Type: {mime_type}\r\n\r\n"
        ).encode("utf-8")
    )
    parts.append(package_path.read_bytes())
    parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))

    body = b"".join(parts)
    request = urllib.request.Request(
        "https://api.threatbook.cn/v3/file/upload",
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "neo-bpsys.PluginMarket automation",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def query_threatbook_report(api_key: str, sha256: str) -> dict[str, Any]:
    query = urllib.parse.urlencode({"apikey": api_key, "sha256": sha256})
    request = urllib.request.Request(
        f"https://api.threatbook.cn/v3/file/report/multiengines?{query}",
        headers={
            "User-Agent": "neo-bpsys.PluginMarket automation",
            "Accept": "application/json",
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def run_threatbook_scan(
    *,
    metadata: PackageMetadata,
    api_key: str,
    timeout_seconds: int,
    min_engines_for_pass: int,
    runtime_seconds: int,
) -> dict[str, Any]:
    upload_result = upload_to_threatbook(metadata.package_path, api_key, runtime_seconds)
    if upload_result.get("response_code") not in (0, None) and not upload_result.get("data"):
        raise PluginMarketError(f"ThreatBook upload failed: {upload_result}")

    started_at = time.time()
    last_payload: dict[str, Any] | None = None
    while time.time() - started_at < timeout_seconds:
        report = query_threatbook_report(api_key, metadata.sha256)
        last_payload = report
        if report.get("response_code") != 0:
            time.sleep(30)
            continue

        scans = (((report.get("data") or {}).get("multiengines") or {}).get("scans") or {})
        if not scans:
            time.sleep(30)
            continue

        total_engines = 0
        safe_engines = 0
        unsafe_engines = 0
        failed_engines = 0
        unsafe_details: list[str] = []

        for engine_name, result in scans.items():
            total_engines += 1
            normalized = result.get("result", "") if isinstance(result, dict) else str(result)
            normalized = normalized.lower()
            if normalized == "safe":
                safe_engines += 1
            elif normalized in {"malicious", "suspicious"}:
                unsafe_engines += 1
                unsafe_details.append(f"{engine_name}: {normalized}")
            else:
                failed_engines += 1

        if unsafe_engines > 0:
            raise PluginMarketError(
                f"ThreatBook detected unsafe results for {metadata.plugin_id}: {', '.join(unsafe_details)}"
            )
        if total_engines < min_engines_for_pass:
            raise PluginMarketError(
                f"ThreatBook returned only {total_engines} engines for {metadata.plugin_id}; "
                f"at least {min_engines_for_pass} are required for automatic verification."
            )

        return {
            "totalEngines": total_engines,
            "safeEngines": safe_engines,
            "failedEngines": failed_engines,
            "reportUrl": f"https://s.threatbook.com/report/file/{metadata.sha256}",
        }

    raise PluginMarketError(f"Timed out waiting for ThreatBook scan results: {last_payload}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Download, verify, and optionally checksum a plugin package.")
    parser.add_argument("--manifest-path", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--download-dir", default=".tmp/plugin-market/downloads")
    parser.add_argument("--verified-result-path", default=".tmp/plugin-market/verified-result.json")
    parser.add_argument("--repo")
    parser.add_argument("--token")
    parser.add_argument("--release-tag")
    parser.add_argument("--asset-name")
    parser.add_argument("--max-auto-verify-size", type=int, default=DEFAULT_MAX_AUTOVERIFY_SIZE)
    parser.add_argument("--sandbox-timeout", type=int, default=DEFAULT_SANDBOX_TIMEOUT)
    parser.add_argument("--min-engines-for-pass", type=int, default=DEFAULT_MIN_ENGINES)
    parser.add_argument("--sandbox-runtime", type=int, default=DEFAULT_SANDBOX_RUNTIME)
    parser.add_argument("--allow-basic-scan-without-api-key", action="store_true")
    parser.add_argument("--manual-review-approved", action="store_true")
    args = parser.parse_args()

    manifest_path = Path(args.manifest_path).resolve()
    download_dir = ensure_directory(Path(args.download_dir).resolve())
    verified_result_path = Path(args.verified_result_path).resolve()
    store = GitHubReleaseChecksumStore(
        repo=args.repo,
        token=args.token,
        release_tag=args.release_tag,
        asset_name=args.asset_name,
    )

    write_github_output("status", "failed")
    try:
        metadata = fetch_package(manifest_path, download_dir)
        write_github_output("plugin_id", metadata.plugin_id)
        write_github_output("sha256", metadata.sha256)
        write_github_output("file_size_bytes", metadata.file_size_bytes)
        write_github_output("file_size_mb", metadata.file_size_mb)

        current_checksums = store.load_checksums()
        stored_checksum = current_checksums.get(metadata.plugin_id, "")
        write_github_output("stored_checksum", stored_checksum)
        write_github_output("checksum_present", str(bool(stored_checksum)).lower())
        write_github_output("checksum_matches", str(stored_checksum == metadata.sha256).lower())

        if metadata.file_size_bytes > args.max_auto_verify_size:
            if args.manual_review_approved:
                store.upsert_checksum(metadata.plugin_id, metadata.sha256)
                write_github_output("stored_checksum", metadata.sha256)
                write_github_output("checksum_present", "true")
                write_github_output("checksum_matches", "true")

            result_path = create_verified_result(
                metadata=metadata,
                head_sha=args.head_sha,
                needs_manual_review=True,
                output_path=verified_result_path,
            )
            status = "manual-review-complete" if args.manual_review_approved else "manual-review-required"
            write_github_output("status", status)
            write_github_output("needs_manual_review", "true")
            write_github_output("verified_result_path", str(result_path))
            log(
                f"{metadata.plugin_id} exceeds the automatic verification size limit "
                f"({metadata.file_size_mb:.2f} MiB > {args.max_auto_verify_size / (1024 * 1024):.2f} MiB)."
            )
            if args.manual_review_approved:
                log(f"Manual review approval detected; stored SHA-256 for {metadata.plugin_id} in release asset.")
            return 0

        api_key = os.environ.get("THREAT_BOOK_API_KEY", "").strip()
        scan_summary: dict[str, Any] = {"mode": "basic"}
        if api_key:
            scan_summary = run_threatbook_scan(
                metadata=metadata,
                api_key=api_key,
                timeout_seconds=args.sandbox_timeout,
                min_engines_for_pass=args.min_engines_for_pass,
                runtime_seconds=args.sandbox_runtime,
            )
        elif args.allow_basic_scan_without_api_key:
            warn(
                "THREAT_BOOK_API_KEY is not configured; automatic verification is falling back to ZIP integrity checks only."
            )
        else:
            raise PluginMarketError(
                "THREAT_BOOK_API_KEY is not configured. Small packages require ThreatBook sandbox verification."
            )

        store.upsert_checksum(metadata.plugin_id, metadata.sha256)
        write_github_output("stored_checksum", metadata.sha256)
        write_github_output("checksum_present", "true")
        write_github_output("checksum_matches", "true")
        result_path = create_verified_result(
            metadata=metadata,
            head_sha=args.head_sha,
            needs_manual_review=False,
            output_path=verified_result_path,
        )
        write_github_output("status", "verified")
        write_github_output("needs_manual_review", "false")
        write_github_output("verified_result_path", str(result_path))
        write_github_output("report_url", scan_summary.get("reportUrl", ""))
        log(f"Verified {metadata.plugin_id} and stored SHA-256 in release asset.")
        return 0
    except Exception as exc:  # noqa: BLE001
        write_github_output("error_message", str(exc))
        error(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
