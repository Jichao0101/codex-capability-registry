---
name: conversation-to-knowledge-candidate
description: 从当前对话中提炼可复用经验，并输出结构化知识候选卡片、source note 或 promotion proposal。适用于用户要求“总结本次对话中值得沉淀的经验”“提炼可复用 knowledge”“复盘一次调试、设计或实现过程”“把对话转成知识库候选条目”“找出本次讨论中的工程原则、反模式、边界条件、验证方法或决策规则”。也适用于用户没有明确要求沉淀，但复杂调试、设计评审、实现讨论或工程决策已经形成可能可复用的经验、约束、失败模式、验证方法、取舍依据或知识候选，需要主动识别 knowledge candidate 的场景。不要用于普通对话摘要、只要最终结论或下一步行动、对话中没有可复用信息、内容主要来自外部资料但尚未建立 source note 或明确来源证据、事实检索/历史证据包/重复候选排查、知识库结构迁移索引/current 文档组/正式提升/写入前治理等场景。
---

# Conversation To Knowledge Candidate

使用本 skill 将对话转成可复用知识材料。输出应以 proposal 为先：候选卡片、source note 或 promotion proposal。不得直接提升正式知识，也不得绕过目标知识库的写入治理。

本 skill 不是记忆系统、普通对话摘要工具、检索器、证据验证器或知识库迁移工具。

## 边界

- 只使用对话内容和用户显式提供的上下文；除非用户授权，不读取本地知识库路径或外部来源。
- 区分已观察事实和 agent 推理；推理必须显式标注。
- 用户偏好和一次性决策默认视为本次任务上下文；除非用户要求保留，或已有跨对话证据表明它是稳定偏好。
- 对话中的外部资料不得直接变成正式知识；除非已经通过目标知识库策略审核，否则只能建议进入 `03_Inbox/` 或 `04_Sources/`。
- 不写入、不提升、不替代结论、不提高 evidence level、不编辑 current 文档组；这些动作必须由 `knowledge-base-structure-builder` 执行对应 gate。
- 如果目标知识库存在 `AGENTS.md`，以它作为策略权威。

## 主动触发门禁

主动触发时保持低打扰。回答结束只触发检查，不等于应该沉淀。

只有当当前阶段结束，并伴随以下至少一类知识型产出时，才进入候选评估：

- 推理过程产生了新的约束、边界或禁止条件。
- 形成了明确选择、取舍或决策依据。
- 发现了异常、失败、误判或回归原因。
- 产生了验证结论、测试策略或证据判断。
- 抽象出了可复用方法、规则、检查项或流程。

不要在普通问答、短对话、事实解释、临时执行细节、一次性命令、路径、文件名或参数后触发。conversation-to-knowledge 的主要风险是把 `task_context` 错当成 knowledge；缺少知识型阶段事件时保持 silent。

主动触发前执行三项判断：

1. `candidate_value`：候选是否值得沉淀。
   - `0`：`task_only`，只对当前请求有用。
   - `1`：`project_local`，可能只对当前项目有用。
   - `2`：`cross_project_candidate`，可能跨项目复用。
   - `3`：`strong_candidate`，能形成方法、失败模式、约束、验证模式或决策启发式。
2. `evidence_readiness`：证据是否足以支撑 proposal。
   - `0`：弱推断或未验证假设。
   - `1`：有对话证据，但范围、边界或风险不完整。
   - `2`：有明确证据，并能说明适用范围与不适用边界。
   - `3`：有证据、边界、风险、反例或验证方式，适合形成候选卡片。
3. `scope_consistency`：候选是否与后续对话和最终结论一致。
   - `consistent`：未被后续对话推翻，适用范围清晰，和最终结论一致。
   - `narrowed`：后续对话收窄了适用范围，可保留但必须写明边界。
   - `superseded`：后续对话替代了前面判断；不生成旧候选，只保留最终验证后的经验。
   - `unresolved`：仍存在冲突、分歧或未验证假设；不主动输出候选，只可列为 `unresolved_items`。

输出阈值：

- `candidate_value = 0`：保持 silent。
- `candidate_value = 1` 且 `evidence_readiness <= 1`：保持 silent。
- `candidate_value = 1` 且 `evidence_readiness >= 2` 且 `scope_consistency = consistent|narrowed`：只在 final 末尾给一句 hint。
- `candidate_value >= 2` 且 `evidence_readiness >= 1` 且 `scope_consistency = consistent|narrowed`：可输出简短 proposal。
- `candidate_value >= 2` 且 `evidence_readiness >= 2` 且 `scope_consistency = consistent`：输出 1-3 条 brief proposal。
- `candidate_value = 3` 且 `evidence_readiness >= 2` 且 `scope_consistency = consistent`：可建议整理为完整候选包，但不默认输出 YAML。
- `scope_consistency = superseded|unresolved`：不主动输出候选；旧判断被替代时只保留最终经验，未解决冲突只记录 unresolved 或保持 silent。

若用户没有要求写入，只提示“可沉淀为候选”，不得询问或暗示已经写入。

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

### 5. 选择输出模式

用户显式要求沉淀时，输出完整结构：

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

skill 主动触发时，根据门禁结果选择低打扰输出模式：

- `silent`：不输出。用于普通问答、`task_only`、低证据内容、冲突未解决内容。
- `hint`：只在 final 末尾给一句轻量提示。
- `brief_proposal`：列 1-3 条候选，每条只包含标题、为什么值得沉淀、建议位置和主要边界。
- `full_package`：只有用户明确要求“整理为候选包 / 输出 YAML / 准备写入”时才使用完整结构。

`brief_proposal` 示例：

```text
这次对话中有 2 条内容值得沉淀为 knowledge candidate：
1. ...
2. ...

它们目前只是 proposal，不会写入知识库。
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
