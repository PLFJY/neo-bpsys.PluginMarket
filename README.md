# neo-bpsys.PluginMarket

[English README](./README_EN.md)

## 插件开发者提交流程

如果你要新增插件或更新已有插件，按下面流程提交即可。

1. Fork 本仓库。
2. 在你自己的仓库中修改或新增 `PluginManifests/<PluginId>.yml`。
3. 确保清单中的 `id` 唯一，且更新插件时不要修改已有 `id`。
4. 补齐或更新插件信息，例如 `name`、`description`、`version`、`apiVersion`、`author`、`icon`、`readme`、`url`、`downloadURL`。
5. 如需本地自检，可执行：

```powershell
python scripts/build-plugin-index.py
```

6. 只提交你修改过的 `PluginManifests/<PluginId>.yml`。
7. 不要提交根目录 `PluginIndex.json`。
8. 向本仓库 `main` 分支发起 Pull Request。

## 重要警告

- `PluginIndex.json` 是自动生成文件，由 GitHub Actions 在合并后自动重建并提交。
- 插件开发者提交 PR 时，不需要也不应该手动修改 `PluginIndex.json`。
- 如果 PR 中包含手动修改的 `PluginIndex.json`，初审 Action 会直接失败，此类变更不予合并。

## 清单要求

- 清单文件放在 `PluginManifests/`
- 文件名建议使用 `<PluginId>.yml`
- 当前只支持扁平的 `key: value` 结构
- 暂不支持嵌套对象或数组
- 每个清单必须包含非空且唯一的 `id`

## 插件信息填写说明

| 字段 | 是否必填 | 说明 | 示例 |
| --- | --- | --- | --- |
| `id` | ✅ | 插件唯一标识，新增后不要随意修改 | `3DViewerIDV` |
| `name` |  | 插件显示名称 | `3DViewerIDV` |
| `description` |  | 插件功能简介 | `3D characters and scene support` |
| `version` | ✅ | 插件版本号 | `0.04` |
| `apiVersion` | ✅ | 适配的宿主 API 版本 | `2.0.0.0` |
| `author` |  | 作者或维护者名称 | `jefcrb` |
| `icon` |  | 插件图标 URL | `https://.../icon.png` |
| `readme` |  | 插件说明文档 URL | `https://.../README.md` |
| `url` |  | 插件项目主页 URL | `https://github.com/...` |
| `downloadURL` | ✅ | 插件包下载地址 | `https://github.com/.../repo-v0.04.zip` |

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

1. 检查是否手动修改了 `PluginIndex.json`。
2. 校验变更的 `PluginManifests/**/*.yml` 是否符合规范。
3. 尝试重建根目录 `PluginIndex.json`，确认清单可以正常生成索引。

如果 PR 通过并合并到 `main`，GitHub Actions 会继续自动：

1. 扫描全部插件清单。
2. 重建根目录 `PluginIndex.json`。
3. 仅在索引内容发生变化时自动提交并推回仓库。

生成后的 `PluginIndex.json` 使用插件 `id` 作为顶层 key。

## 校验规则

- 变更的 `PluginManifests/**/*.yml` 会先做 YAML 语法检查
- 必填字段：`id`、`version`、`apiVersion`、`downloadURL`
- 每一行都必须是合法的扁平 `key: value` 结构
- 以 `#` 开头的行会被当作注释
- 如果清单解析失败、缺少 `id`、出现重复 `id`，或 PR 手动修改了 `PluginIndex.json`，GitHub Action 会失败
