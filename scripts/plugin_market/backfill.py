from __future__ import annotations

import argparse
from pathlib import Path

from plugin_market.checksum_store import GitHubReleaseChecksumStore
from plugin_market.common import (
    MANIFEST_DIR,
    PluginMarketError,
    append_step_summary,
    error,
    log,
    write_github_output,
)
from plugin_market.manifest import load_manifest_map, parse_manifest_text
from plugin_market.package_verify import fetch_package


def summarize_stats(
    *,
    total_manifests: int,
    existing_checksums: int,
    added: int,
    skipped: int,
    failed: int,
) -> str:
    return (
        f"total_manifests={total_manifests}\n"
        f"existing_checksums={existing_checksums}\n"
        f"added={added}\n"
        f"skipped={skipped}\n"
        f"failed={failed}"
    )


def backfill_missing_checksums(
    *,
    store: GitHubReleaseChecksumStore,
    plugin_id_filter: str | None,
    download_dir: Path,
) -> tuple[int, int, int, int, int]:
    manifests = load_manifest_map(MANIFEST_DIR)
    checksums = store.load_checksums()
    existing_checksums = len(checksums)
    added = 0
    skipped = 0
    failed = 0

    for manifest_plugin_id, manifest in manifests.items():
        if plugin_id_filter and manifest_plugin_id != plugin_id_filter:
            skipped += 1
            continue
        if manifest_plugin_id in checksums:
            skipped += 1
            continue

        manifest_path = MANIFEST_DIR / f"{manifest_plugin_id}.yml"
        try:
            metadata = fetch_package(manifest_path, download_dir)
            checksums[manifest_plugin_id] = metadata.sha256
            added += 1
            log(f"Backfilled checksum for {manifest_plugin_id}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            error(f"Failed to backfill {manifest_plugin_id}: {exc}")

    if added > 0:
        store.save_checksums(checksums)

    return len(manifests), existing_checksums, added, skipped, failed


def apply_manual_pr_review(
    *,
    store: GitHubReleaseChecksumStore,
    pr_number: int,
    plugin_id_filter: str | None,
    download_dir: Path,
) -> tuple[str, str]:
    files = store.client.get_pull_request_files(pr_number)
    manifest_paths = [
        file["filename"]
        for file in files
        if isinstance(file.get("filename"), str)
        and file["filename"].startswith("PluginManifests/")
        and file["filename"].endswith(".yml")
    ]
    if len(manifest_paths) != 1:
        raise PluginMarketError(
            f"PR #{pr_number} must change exactly one manifest file before manual approval can write checksum."
        )

    manifest_path = manifest_paths[0]
    manifest_text = store.client.get_file_content(manifest_path, ref=f"refs/pull/{pr_number}/head")
    manifest = parse_manifest_text(manifest_text, f"PR #{pr_number}:{manifest_path}")
    plugin_id = str(manifest.get("id", "")).strip()
    if not plugin_id:
        raise PluginMarketError(f"PR #{pr_number} manifest does not contain a valid id")
    if plugin_id_filter and plugin_id_filter != plugin_id:
        raise PluginMarketError(
            f"Requested plugin id '{plugin_id_filter}' does not match PR #{pr_number} manifest id '{plugin_id}'"
        )

    temp_manifest_dir = download_dir / "pr-manifests"
    temp_manifest_dir.mkdir(parents=True, exist_ok=True)
    temp_manifest_path = temp_manifest_dir / f"{plugin_id}.yml"
    temp_manifest_path.write_text(manifest_text, encoding="utf-8")

    metadata = fetch_package(temp_manifest_path, download_dir)
    checksums = store.load_checksums()
    checksums[plugin_id] = metadata.sha256
    store.save_checksums(checksums)

    store.client.add_labels(pr_number, ["manual-review-approved", "ci:verified"])
    for label in ["ci:manual-review-required", "ci:waiting-sandbox", "ci:precheck-failed", "ci:plugin-conflict"]:
        store.client.remove_label(pr_number, label)
    store.client.create_comment(
        pr_number,
        (
            f"管理员已完成人工处理并写入 checksum。\n\n"
            f"- Plugin: `{plugin_id}`\n"
            f"- SHA-256: `{metadata.sha256}`\n"
            f"- 状态存储: release asset `{store.asset_name}` (`{store.release_tag}`)"
        ),
    )
    return plugin_id, metadata.sha256


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill release checksum state or manually approve a PR package.")
    parser.add_argument("--repo")
    parser.add_argument("--token")
    parser.add_argument("--release-tag")
    parser.add_argument("--asset-name")
    parser.add_argument("--download-dir", default=".tmp/plugin-market/backfill-downloads")
    parser.add_argument("--plugin-id")
    parser.add_argument("--pr-number", type=int)
    args = parser.parse_args()

    store = GitHubReleaseChecksumStore(
        repo=args.repo,
        token=args.token,
        release_tag=args.release_tag,
        asset_name=args.asset_name,
    )
    download_dir = Path(args.download_dir).resolve()
    download_dir.mkdir(parents=True, exist_ok=True)

    try:
        if args.pr_number:
            plugin_id, sha256 = apply_manual_pr_review(
                store=store,
                pr_number=args.pr_number,
                plugin_id_filter=args.plugin_id,
                download_dir=download_dir,
            )
            write_github_output("mode", "manual-pr-review")
            write_github_output("plugin_id", plugin_id)
            write_github_output("sha256", sha256)
            append_step_summary(
                f"## Manual PR checksum write\n\n- PR: #{args.pr_number}\n- Plugin: `{plugin_id}`\n- SHA-256: `{sha256}`\n"
            )
            log(f"Stored checksum for PR #{args.pr_number} plugin {plugin_id}")
            return 0

        total_manifests, existing_checksums, added, skipped, failed = backfill_missing_checksums(
            store=store,
            plugin_id_filter=args.plugin_id,
            download_dir=download_dir,
        )
        summary = summarize_stats(
            total_manifests=total_manifests,
            existing_checksums=existing_checksums,
            added=added,
            skipped=skipped,
            failed=failed,
        )
        write_github_output("mode", "backfill-missing")
        for line in summary.splitlines():
            name, value = line.split("=", 1)
            write_github_output(name, value)
        append_step_summary(
            "## Checksum backfill summary\n\n"
            f"- Manifest total: {total_manifests}\n"
            f"- Existing checksum count: {existing_checksums}\n"
            f"- Added: {added}\n"
            f"- Skipped: {skipped}\n"
            f"- Failed: {failed}\n"
        )
        log(summary)
        return 0
    except Exception as exc:  # noqa: BLE001
        error(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
