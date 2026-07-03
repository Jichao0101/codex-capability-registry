---
name: conversation-to-knowledge-candidate
description: 从当前对话中提炼可复用经验，并输出结构化知识候选卡片、source note 或 promotion proposal。适用于用户要求“总结本次对话中值得沉淀的经验”“提炼可复用 knowledge”“复盘一次调试、设计或实现过程”“把对话转成知识库候选条目”“找出本次讨论中的工程原则、反模式、边界条件或决策规则”，以及需要区分本次任务上下文、项目内约束、跨项目可复用经验、用户偏好、证据缺口和正式知识成熟度的长对话整理场景。
---

# Conversation To Knowledge Candidate

使用本 skill 将对话转成可复用知识材料。输出应以 proposal 为先：候选卡片、source note 或 promotion proposal。不得直接提升正式知识，也不得绕过目标知识库的写入治理。

本 skill 不是记忆系统、普通对话摘要工具、检索器、证据验证器或知识库迁移工具。

## 使用时机

在以下场景使用：

- 用户要求总结本次对话中值得沉淀的经验。
- 用户要求提炼可复用 knowledge、经验、原则、反模式或决策规则。
- 用户要求复盘一次调试、设计、实现、评审或治理过程。
- 用户要求把对话转成知识库候选条目、候选卡片、source note 或 promotion proposal。
- 用户要求找出本次讨论中的工程原则、反模式、边界条件、验证方法或决策规则。
- 对话很长且混合了事实、推理、临时上下文、用户偏好、项目约束和可复用经验，需要做结构化分层。
- 在写入 Markdown 知识库前，需要先形成候选包交给 `knowledge-base-structure-builder` 做 placement、preflight 或 promotion gate。

## 不使用时机

在以下场景不要使用：

- 用户只要普通对话摘要、会议摘要或自然语言 recap。
- 用户只要最终结论、下一步行动或简短决策，不需要知识沉淀。
- 对话中没有明显可复用信息，只有一次性上下文或临时执行细节。
- 用户要求直接修改正式知识库，但尚未经过 `knowledge-base-structure-builder` 的 gate。
- 内容主要来自外部资料，且尚未建立 source note 或明确来源证据。
- 用户要求事实检索、历史证据包、重复候选排查；这种场景优先使用 `knowledge-base-retriever`。
- 用户要求知识库结构、迁移、索引、current 文档组、正式提升或写入前治理；这种场景使用 `knowledge-base-structure-builder`。

## 边界

- 只使用对话内容和用户显式提供的上下文；除非用户授权，不读取本地知识库路径或外部来源。
- 区分已观察事实和 agent 推理；推理必须显式标注。
- 用户偏好和一次性决策默认视为本次任务上下文；除非用户要求保留，或已有跨对话证据表明它是稳定偏好。
- 对话中的外部资料不得直接变成正式知识；除非已经通过目标知识库策略审核，否则只能建议进入 `03_Inbox/` 或 `04_Sources/`。
- 不写入、不提升、不替代结论、不提高 evidence level、不编辑 current 文档组；这些动作必须由 `knowledge-base-structure-builder` 执行对应 gate。
- 如果目标知识库存在 `AGENTS.md`，以它作为策略权威。

## 工作流

### 1. 划分对话材料

把材料分成以下类别：

- `task_context`：只服务于当前请求的细节。
- `project_constraint`：绑定到特定项目或仓库的规则、决策、路径或行为。
- `reusable_experience`：可能跨任务复用的模式、失败模式、启发式、验证方法或集成约束。
- `user_preference`：看起来可能稳定的用户偏好、工作流习惯或输出期待。
- `external_source`：对话中提到的网页、论文、邮件、聊天、会议或第三方信息。
- `uncertain_or_conflicting`：需要验证、互相冲突或依赖缺失上下文的说法。

每项只保留最小有用摘录或转述，避免复制大段对话。

### 2. 识别经验类型

为每个可复用项目选择一个主要类型：

- `pattern`：可重复的方法或设计方式。
- `failure_mode`：常见 bug、陷阱、回归或误导性假设。
- `constraint`：必须遵守的规则。
- `validation`：测试、评审、测量或证据模式。
- `decision_heuristic`：在多个选项之间做选择的实用规则。
- `workflow`：可重复执行的步骤序列。
- `tooling`：命令、脚本用法或自动化边界。
- `preference`：用户特定习惯或稳定协作期待。

### 3. 判断复用级别

使用能被证据支撑的最低级别：

- `task_only`：只对本次对话有用；除非用户明确要求，不生成候选。
- `project_local`：只在单个项目内有用；建议进入 `02_Projects/`。
- `cross_project_candidate`：可能跨项目复用，但仍未审核；建议进入 `03_Inbox/`。
- `source_note`：绑定来源的证据或摘录；建议进入 `04_Sources/`。
- `promotion_proposal`：看起来具备正式审核价值，但进入 `01_Knowledge/` 前仍必须经过 Builder 或人工 gate。

正式知识至少需要 summary、source、scope、risks 或 boundaries、status。缺少任一项都应列为 promotion blocker。

### 4. 建议沉淀位置

只建议位置，不直接应用：

- `02_Projects/`：项目特定约束、决策、实验、实现记录或当前任务记录。
- `03_Inbox/`：未审核的可复用候选、对话提炼出的启发式、尚不确定但有价值的经验。
- `04_Sources/`：source note、原始摘录、网页/论文/邮件证据卡、作为证据保留的对话记录。
- `01_Knowledge/`：只能作为 `promotion_proposal`，不得自动直接写入。

如果缺少授权路径，输出 `placement: needs_authorization` 并列出缺少的授权范围。

### 5. 输出候选卡片

优先输出少量高价值卡片，而不是穷尽所有片段。只保留确有复用价值、或用户明确要求保存的内容。

```yaml
conversation_knowledge_package:
  version: 1
  source_scope:
    conversation_range: "current conversation"
    additional_sources_read: []
    authorized_paths: []
  candidates:
    - title:
      experience_type:
      reuse_level:
      recommended_placement:
      summary:
      source:
        kind: conversation
        evidence: "short paraphrase or brief excerpt"
      scope:
      risks_or_boundaries:
      confidence: low|medium|high
      status: draft|pending_review|proposal_only
      promotion_blockers: []
      next_action:
  source_notes:
    - title:
      recommended_placement: "04_Sources/"
      source_kind:
      source_summary:
      evidence_to_preserve:
      risks_or_boundaries:
  promotion_proposals:
    - title:
      proposed_target:
      why_reusable:
      evidence_summary:
      required_review:
      missing_fields: []
  ignored_material:
    - reason:
      summary:
  unresolved_items: []
```

## 质量要求

- 少量高质量候选优先于穷尽式抽取。
- 保留不确定性；不要把弱判断写成已验证结论。
- 候选标题应面向可复用经验，不要绑定到单个时间戳或单轮聊天。
- 必须写出反向边界：经验在哪些场景不适用、缺少什么证据、什么情况会推翻它。
- 项目绑定内容必须说明：要跨项目复用前还需要抽象出什么。
- 用户偏好不得自动泛化为全局偏好；除非用户明确要求保存为稳定偏好知识。

## 与其他知识库 skill 协作

只有当用户授权本地路径、且需要历史上下文来避免重复或冲突候选时，才先使用 `knowledge-base-retriever`。

任何实际知识库写入、索引更新、current 文档组变更、正式提升、source note 创建或 preflight，都交给 `knowledge-base-structure-builder`。本 skill 可以准备供 Builder 评估的候选包；Builder 负责 placement gate、受保护文档处理、索引同步和正式提升。
