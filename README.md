# neo-bpsys.PluginMarket

[English README](./README_EN.md)

## 插件开发者提交流程

如果你要新增插件或更新已有插件，按下面流程提交即可。

1. Fork 本仓库。
2. 在你自己的仓库中修改或新增 `PluginManifests/<PluginId>.yml`。
3. 确保清单中的 `id` 唯一，且更新插件时不要修改已有 `id`。
4. 补齐或更新插件信息，例如 `name`、`description`、`version`、`apiVersion`、`author`、`icon`、`readme`、`url`、`downloadURL`。
5. **不要填写 `sha256`。** SHA-256 由仓库自动校验流程生成并写入 release 状态存储。
6. 如需本地自检，可执行：

```powershell
python scripts/build-plugin-index.py
```

6. 只提交你修改过的 `PluginManifests/<PluginId>.yml`。
7. **不要提交根目录 `PluginIndex.json`。**
8. **不要提交或手动维护 `checksums.json`。**
9. 向本仓库 `main` 分支发起 Pull Request。

## 重要警告

- `PluginIndex.json` 是自动生成文件，由 GitHub Actions 在合并后自动重建并提交。
- `sha256` 不由插件作者填写。正式 checksum 状态保存在固定 release 的 `checksums.json` asset 中。
- 小文件在自动校验通过后会直接写入 checksum；大文件可能进入人工处理流程。
- 插件开发者提交 PR 时，不需要也不应该手动修改 `PluginIndex.json`。
- 插件开发者提交 PR 时，不需要也不应该手动维护 `checksums.json`。
- 如果 PR 中包含手动修改的 `PluginIndex.json`，初审 Action 会直接失败，此类变更不予合并。

## 清单要求

- 清单文件放在 `PluginManifests/`
- 文件名建议使用 `<PluginId>.yml`
- 清单文件名必须与清单中的 `id` 一致
- 当前只支持扁平的 `key: value` 结构
- 暂不支持嵌套对象或数组
- 每个清单必须包含非空且唯一的 `id`
- 插件包解压后必须包含且只包含一个 `manifest.yml`，其中的 `id` 必须与市场清单文件名、市场清单中的 `id` 完全一致

## 插件信息填写说明

| 字段 | 是否必填 | 说明 | 示例 |
| --- | --- | --- | --- |
| `id` | ✅ | 插件唯一标识，新增后不要随意修改 | `3DViewerIDV` |
| `name` |  | 插件显示名称 | `3DViewerIDV` |
| `description` |  | 插件功能简介 | `3D characters and scene support` |
| `version` | ✅ | 插件版本号，必须是可转换为 .NET `Version` 对象的纯数字版本号 | `1.0.0` |
| `apiVersion` | ✅ | 适配的宿主 API 版本，必须是可转换为 .NET `Version` 对象的纯数字版本号 | `2.0.0.0` |
| `author` |  | 作者或维护者名称 | `jefcrb` |
| `icon` |  | 插件图标 URL | `https://.../icon.png` |
| `readme` |  | 插件说明文档 URL | `https://.../README.md` |
| `url` |  | 插件项目主页 URL | `https://github.com/...` |
| `downloadURL` | ✅ | 插件包下载地址 | `https://github.com/.../repo-v0.04.zip` |
| `sha256` | ❌ | **不要填写**。由系统在校验/人工处理后自动写入发布状态并注入 `PluginIndex.json` | |

示例：

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

## 常见提交场景

### 新增插件

- 新建一个自己的 `PluginManifests/<PluginId>.yml`
- 首次填写完整元数据
- 不要提交 `PluginIndex.json`

### 更新插件

- 修改自己已有的清单文件
- 更新版本号、下载地址或描述等信息
- 保持原有 `id` 不变
- 不要提交 `PluginIndex.json`

## 仓库自动化说明

当 PR 提交到 `main` 时，GitHub Actions 会先进行初审：

1. 检查 PR 是否只修改了一个 `PluginManifests/<PluginId>.yml`。
2. 拒绝手动修改 `PluginIndex.json` 或 `checksums.json`。
3. 校验 manifest 的扁平结构、必填字段、文件名与 `id` 一致性，以及同插件 open PR 冲突。
4. 下载插件包，检查包内存在唯一的 `manifest.yml`，并校验包内 `id` 与市场清单文件名、市场清单中的 `id` 完全一致。
5. 计算插件包 SHA-256。
6. 小文件走自动校验，校验通过后立即把 checksum 写入 release asset `checksums.json`。
7. 大文件会被标记为人工处理，等待管理员手动 workflow 写入 checksum。

如果 PR 通过并合并到 `main`，GitHub Actions 会继续自动：

1. 扫描全部插件清单。
2. 从 release asset `checksums.json` 读取正式 checksum 状态。
3. 重建根目录 `PluginIndex.json`，并为每个插件条目追加 `sha256`。
4. 仅在索引内容发生变化时自动提交并推回仓库。

生成后的 `PluginIndex.json` 使用插件 `id` 作为顶层 key。

管理员还可以手动触发 `backfill-missing-checksums` workflow，用于：

1. 为当前 `main` 分支里已存在、但 release `checksums.json` 中缺失 checksum 的插件补齐 hash。
2. 对大文件 PR 完成人工处理后，按 PR 编号写入对应 checksum，并自动补上 `manual-review-approved` / `ci:verified` 标签。

## 校验规则

- 变更的 `PluginManifests/**/*.yml` 会先做 YAML 语法检查
- 必填字段：`id`、`version`、`apiVersion`、`downloadURL`
- `version` 和 `apiVersion` 必须是可转换为 .NET `Version` 对象的纯数字版本号
- 每一行都必须是合法的扁平 `key: value` 结构
- `PluginManifests/<PluginId>.yml` 的文件名必须和 manifest 中的 `id` 一致
- 插件包内必须包含且只包含一个 `manifest.yml`，其中的 `id` 必须与市场清单文件名和市场清单中的 `id` 一致
- 以 `#` 开头的行会被当作注释
- 如果清单解析失败、缺少 `id`、出现重复 `id`，或 PR 手动修改了 `PluginIndex.json`，GitHub Action 会失败
