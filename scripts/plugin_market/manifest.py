from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

from plugin_market.common import MANIFEST_DIR, PluginMarketError


REQUIRED_FIELDS = ("id", "version", "apiVersion", "downloadURL")
ALLOWED_MANIFEST_PATH = re.compile(r"^PluginManifests/[^/]+\.yml$")
DOTNET_VERSION_PATTERN = re.compile(r"^\d+\.\d+(?:\.\d+){0,2}$")


def parse_scalar(raw_value: str) -> str:
    value = raw_value.strip()
    if not value:
        return ""

    if value.startswith('"') and value.endswith('"'):
        return json.loads(value)

    if value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("''", "'")

    return value


def parse_manifest_text(text: str, source: str) -> dict[str, str]:
    text = text.lstrip("\ufeff")
    manifest: dict[str, str] = {}

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if raw_line[:1].isspace():
            raise PluginMarketError(
                f"{source}: line {line_number} uses indentation; only flat key/value manifests are supported"
            )

        key, separator, value = raw_line.partition(":")
        if not separator:
            raise PluginMarketError(f"{source}: line {line_number} is not a valid key/value pair")

        key = key.strip()
        if not key:
            raise PluginMarketError(f"{source}: line {line_number} has an empty key")
        if key in manifest:
            raise PluginMarketError(f"{source}: duplicate key '{key}'")

        manifest[key] = parse_scalar(value)

    return manifest


def parse_manifest_file(path: Path) -> dict[str, str]:
    return parse_manifest_text(path.read_text(encoding="utf-8"), str(path))


def validate_dotnet_version(value: str) -> bool:
    return bool(DOTNET_VERSION_PATTERN.fullmatch(value.strip()))


def validate_manifest(
    manifest: dict[str, str],
    *,
    source: str,
    manifest_path: str | None = None,
) -> list[str]:
    errors: list[str] = []

    for field in REQUIRED_FIELDS:
        if field not in manifest or not str(manifest[field]).strip():
            errors.append(f"{source}: missing required field '{field}'")

    for field in ("version", "apiVersion"):
        if field in manifest and str(manifest[field]).strip() and not validate_dotnet_version(str(manifest[field])):
            errors.append(
                f"{source}: field '{field}' must be a numeric .NET-style version like '1.0.0' or '2.0.0.0'"
            )

    if manifest_path:
        file_name = Path(manifest_path).name
        expected_file_name = f"{manifest.get('id', '').strip()}.yml"
        if manifest.get("id") and file_name != expected_file_name:
            errors.append(
                f"{source}: file name must match manifest id ('{expected_file_name}' expected, got '{file_name}')"
            )

    return errors


def ensure_manifest_path_allowed(path: str) -> None:
    if not ALLOWED_MANIFEST_PATH.fullmatch(path):
        raise PluginMarketError(
            f"{path}: only a single file matching 'PluginManifests/<PluginId>.yml' may be changed"
        )


def load_manifest_map(
    manifest_dir: Path = MANIFEST_DIR,
    *,
    exclude_paths: Iterable[Path] | None = None,
) -> dict[str, dict[str, str]]:
    if not manifest_dir.exists():
        raise PluginMarketError(f"Manifest directory not found: {manifest_dir}")

    excluded = {path.resolve() for path in (exclude_paths or [])}
    manifests: dict[str, dict[str, str]] = {}

    for manifest_path in sorted(manifest_dir.glob("*.yml")):
        if manifest_path.resolve() in excluded:
            continue

        manifest = parse_manifest_file(manifest_path)
        errors = validate_manifest(manifest, source=str(manifest_path), manifest_path=str(manifest_path))
        if errors:
            raise PluginMarketError("\n".join(errors))

        plugin_id = manifest["id"]
        if plugin_id in manifests:
            raise PluginMarketError(f"Duplicate plugin id '{plugin_id}' found in {manifest_path}")
        manifests[plugin_id] = manifest

    return manifests
