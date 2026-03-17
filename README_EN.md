# neo-bpsys.PluginMarket

[中文 README](./README.md)

## Plugin Submission Flow

If you want to add a new plugin or update an existing one, follow this process.

1. Fork this repository.
2. In your fork, add or edit `PluginManifests/<PluginId>.yml`.
3. Make sure the manifest `id` is unique, and do not change the existing `id` when updating a plugin.
4. Fill in or update plugin metadata such as `name`, `description`, `version`, `apiVersion`, `author`, `icon`, `readme`, `url`, and `downloadURL`.
5. If you want to verify locally, run:

```powershell
python scripts/build-plugin-index.py
```

6. Commit only the manifest file you changed under `PluginManifests/`.
7. Do not commit the root `PluginIndex.json`.
8. Open a Pull Request against the `main` branch.

## Important Warning

- `PluginIndex.json` is a generated file and is rebuilt automatically by GitHub Actions after merge.
- Plugin authors do not need to and must not edit `PluginIndex.json` manually in a PR.
- If a PR includes manual changes to `PluginIndex.json`, the pre-check Action will fail and the change will not be merged.

## Manifest Requirements

- Manifest files must be placed under `PluginManifests/`
- Recommended file name: `<PluginId>.yml`
- Only flat `key: value` structure is supported
- Nested objects and arrays are not supported
- Every manifest must contain a non-empty and unique `id`

## Manifest Field Reference

| Field | Required | Description | Example |
| --- | --- | --- | --- |
| `id` | ✅ | Unique plugin identifier. Do not change it after the plugin is published. | `3DViewerIDV` |
| `name` |  | Display name of the plugin | `3DViewerIDV` |
| `description` |  | Short summary of what the plugin does | `3D characters and scene support` |
| `version` | ✅ | Plugin version | `0.04` |
| `apiVersion` | ✅ | Host API version supported by the plugin | `2.0.0.0` |
| `author` |  | Author or maintainer name | `jefcrb` |
| `icon` |  | URL to the plugin icon | `https://.../icon.png` |
| `readme` |  | URL to the plugin README | `https://.../README.md` |
| `url` |  | Project homepage URL | `https://github.com/...` |
| `downloadURL` | ✅ | Download URL for the installable package | `https://github.com/.../repo-v0.04.zip` |

Example:

```yml
id: "3DViewerIDV"
name: "3DViewerIDV"
description: "3D characters and scene support"
version: "0.04"
apiVersion: "2.0.0.0"
author: "jefcrb"
icon: "https://raw.githubusercontent.com/jefcrb/3DViewerIDV/refs/heads/master/icon.png"
readme: "https://raw.githubusercontent.com/jefcrb/3DViewerIDV/refs/heads/master/README.md"
url: "https://github.com/jefcrb/3DViewerIDV"
downloadURL: "https://github.com/jefcrb/3DViewerIDV/releases/download/v0.04/repo-v0.04.zip"
```

## Common Cases

### Add a New Plugin

- Create your own `PluginManifests/<PluginId>.yml`
- Fill in the initial metadata
- Do not commit `PluginIndex.json`

### Update an Existing Plugin

- Edit your existing manifest file
- Update fields such as version, download URL, or description
- Keep the original `id`
- Do not commit `PluginIndex.json`

## Repository Automation

When a PR targets `main`, GitHub Actions first runs a pre-check to:

1. Detect manual changes to `PluginIndex.json`.
2. Validate changed `PluginManifests/**/*.yml` files.
3. Rebuild the root `PluginIndex.json` to confirm the manifests can generate a valid index.

After the PR is merged into `main`, GitHub Actions will:

1. Scan all manifests.
2. Rebuild the root `PluginIndex.json`.
3. Commit and push it only if the generated content changed.

The generated `PluginIndex.json` uses plugin `id` as the top-level key.

## Validation Rules

- Changed `PluginManifests/**/*.yml` files are checked for YAML syntax first
- Required fields: `id`, `version`, `apiVersion`, `downloadURL`
- Each line must be a valid flat `key: value` pair
- Lines starting with `#` are treated as comments
- If parsing fails, `id` is missing, duplicate `id` values are found, or the PR manually changes `PluginIndex.json`, the GitHub Action fails
