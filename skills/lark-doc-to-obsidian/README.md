# lark-doc-to-obsidian

将单篇飞书文档导入为本地 Obsidian Markdown 笔记。

## 功能

- 支持输入飞书 wiki URL 或 wiki token
- 使用已登录的 `lark-cli` 读取文档内容
- 解析 wiki 节点后，仅导入 `docx` 类型文档
- 将正文基础结构转换为 Markdown
- 将部分富对象导出到本地 `.assets/` 目录
- 将导出的图片以本地相对路径插入文档
- 对无法稳定导出的对象保留 placeholder
- 校验当前文档中指向当前附件目录的本地链接

## 当前支持

- 单篇文档导入
- `docx` 正文抓取
- 普通图片导出与插入
- whiteboard 导出为图片并插入文档
- 本地 Markdown 落盘
- 当前文档附件链接检查

## 当前不支持

- 批量导入
- 双向同步
- OCR
- 评论 / 批注 / 修订记录同步
- 自动知识分类
- 全库扫描或修改既有笔记
- `mention-doc` 递归展开
- `sheet / grid / bitable / slides / file / mindnote` 完整导出

## 依赖

- `lark-cli`
- 已登录的飞书用户身份
- 本地 Obsidian vault

## 工作流程

1. 解析 wiki URL 或 wiki token
2. 执行：

   ```bash
   lark-cli wiki spaces get_node --params '{"token":"<wiki_token>"}'
   ```

3. 读取 `obj_type` 和 `obj_token`
4. 若 `obj_type == "docx"`，执行：

   ```bash
   lark-cli docs +fetch --doc <obj_token>
   ```

5. 提取正文 Markdown 与标题
6. 转换正文内容并处理富对象
7. 将 Markdown 和附件写入本地 vault
8. 校验当前文档中的本地附件链接
9. 输出导入摘要

## 路径规则

- 优先使用显式 `--note-path`
- 若只提供 `--note-dir`，文件名默认为 `<document-title>.md`
- 附件目录默认为 `<note_stem>.assets/`

## 链接规则

- 外部网页链接保留原始 URL
- 飞书文档引用不做递归展开
- 本次导出的本地附件使用相对路径
- 不扫描整个 vault，不修改其他笔记

## 安全规则

- 默认不覆盖已有 note
- 若目标 note 已存在，直接报错
- 若附件部分导出失败，正文仍可写入，但会保留 placeholder 和失败说明

## 输出结果

每次导入会生成：

- 一个 Markdown 文件
- 一个同名 `.assets/` 附件目录（如有附件）
- 一份导入摘要

导入摘要通常包含：

- 文档标题
- 输出路径
- 附件目录
- Markdown 转换数量
- 图片导出数量
- placeholder 数量
- 本地附件链接检查结果

## 适用场景

适合：

- 将单篇飞书文档沉淀到 Obsidian
- 保留正文和部分图片/whiteboard 快照
- 作为候选知识进入本地知识库

不适合：

- 做飞书全量同步
- 递归抓取整套知识文档
- 高保真重建所有富对象结构

## 示例

```bash
python scripts/import_lark_doc.py \
  --input "https://horizonrobotics.feishu.cn/wiki/xxxx" \
  --vault "/path/to/vault" \
  --note-dir "03_Inbox"
```

## 当前版本说明

当前版本的定位是：

> 单篇飞书 `docx` 文档导入器，支持 Markdown 转换、图片/whiteboard 快照导出，以及占位降级。

它不是全功能飞书同步器。
