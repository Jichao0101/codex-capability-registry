---
name: interface-abstraction-implementation-guard
description: 用于非机械代码修改的实现阶段，约束 public/private API、内部抽象、helper 拆分、新增类型、模块边界、行为契约和重构 plan step，确保实现不偏离最近的 deep-module-design-review 结论或用户批准方案。若没有评审结论但任务明显涉及接口或抽象变动，本 skill 只执行最小前置审计，并在实现后要求 diff 审计。不要用于纯格式化、拼写、单行平凡修复、依赖版本更新、生成文件刷新，或用户明确禁止设计/抽象检查的实现任务。
---

# 接口与抽象实现守门

## 1. 定位

本 skill 用作实现阶段守门，不重新做大范围模块设计评审。它把最近批准的设计评审结论或用户方案转换为具体实现约束，并检查最终 diff 是否仍在约束范围内。

核心目标：

- 保证 public/private API 修改不超出已批准计划。
- 防止未经评审的 helper 拆分、wrapper、context/result payload 和新增内部抽象扩大认知接口。
- 除非明确授权，否则保持行为边界、失败模型、ownership、生命周期和调用方责任不变。
- 在完成前发现抽象漂移和 API 漂移。

## 2. 与 `deep-module-design-review` 的关系

`deep-module-design-review` 用于分析和规划。本 skill 用于实现。

若存在近期评审结论，把它视为设计事实源：

- 提取允许项、禁止项、风险边界、plan step、验证策略和停止条件。
- 只实现当前 active plan step 或明确批准的子集。
- 除非实现中命中停止条件，否则不重新打开大设计问题。

若没有评审结论，但实现任务明显触及接口或抽象边界，只执行第 5 节的最小前置审计。若审计发现非局部设计风险，应停止并建议先执行 `deep-module-design-review`。

## 3. 触发与排除

实现或重构代码时，若满足以下任一条件，使用本 skill：

- 新增、删除、重命名或修改 public API、private header API、internal API、方法签名、导出类型、callback 或跨模块数据契约。
- 新增或重组 `class`、`struct`、`enum`、`View`、`Payload`、`Context`、`Row`、`Result`、wrapper、helper object、strategy object、parser、mapper、cache、state owner 或 lifecycle owner。
- 把大函数拆成 helper、合并 helper、跨文件移动 helper，或改变 helper 可见性。
- 实现先前设计评审计划中的某一步。
- 改变行为边界：错误处理、fallback 规则、顺序、副作用、持久化/序列化形态、并发语义、ownership、生命周期或调用方责任。

以下情况不要使用本 skill：

- 纯格式化、拼写、import 清理、生成文件刷新或构建元数据修改。
- 小型机械替换，且 API、抽象、helper 结构和行为边界均不变。
- 紧急 hot patch，且用户明确要求最窄缺陷修复、不要重构。
- 只做评审、不进入实现的任务。

## 4. 实现流程

### 第一步：查找设计事实源

编辑前按以下顺序寻找最近适用来源：

1. 当前对话中用户提供的实现方案。
2. repo、issue、PR 或任务记录中近期的 `deep-module-design-review` 结论或评审工件。
3. 说明当前契约的模块文档、设计记录、测试或代码注释。
4. 第 5 节的最小前置审计。

只读取能确认契约的最小相关上下文。不要基于未读取文件推断事实。

### 第二步：提取实现守门信息

编辑前写出或在工作上下文中明确以下简短 guardrail：

```text
设计来源：
当前 plan step：
允许修改：
禁止修改：
行为/API 不变量：
允许新增的抽象或类型：
明确拒绝或暂缓的抽象：
风险边界：
停止条件：
验证方式：
```

保持简短。该块用于约束实现，不要扩展成新的设计评审。

### 第三步：声明当前 plan step

修改代码前，声明本次正在实现哪个已批准步骤。

若任务横跨多个 step，按顺序分别实现。不要把低风险清理和边界变更静默合并，除非设计来源明确允许。

### 第四步：在 guardrail 内实现

实现中必须遵守：

- 除非当前 step 明确授权，否则保持 public API 不变。
- 把 private header 中的方法和类型也视为维护者必须理解的 API surface；默认不要在其中加入 step-level 执行脚本或临时 payload。
- 新增持久类型前，优先复用已有 domain object、容器、局部变量、局部 lambda、函数局部 struct 或 `.cpp`/internal helper。
- 只有当新类型已在批准清单中，或通过第 6 节最小抽象检查时，才允许新增。
- helper 提取优先保持 phase-level 语义；避免把固定顺序执行链暴露成一组 step helper。
- 不新增只用于把数据从一步搬到下一步的 wrapper。
- 不用注释、测试或命名为缺少不变量、生命周期、稳定职责或复用价值的抽象做事后辩护。
- 除非当前 step 授权，否则不改变行为、失败模型、执行顺序、状态 ownership 或副作用。

如果实现中发现 guardrail 外的新需求，先停止，不要继续编码该部分。记录偏差，并请求用户批准或对新增点执行最小前置审计。

## 5. 无评审结论时的最小前置审计

仅在没有近期设计评审或批准方案，且实现看起来会触及 API 或抽象边界时使用。

简要回答：

```text
当前 public/private 契约：
拟改变的边界：
是否可在不改变 API 或抽象的前提下实现：
可复用的现有表示：
新增 helper/type 候选：
各候选为何必要或不必要：
行为风险：
最小安全实现步骤：
需要完整设计评审的停止条件：
```

只有当结论是局部、低风险实现步骤时，才继续。出现以下任一情况，应停止并建议先执行 `deep-module-design-review`：

- 需要修改 public API、序列化、协议、持久化、并发、生命周期或失败模型。
- 多个模块或调用方必须围绕新契约协同。
- 新抽象需要在未批准设计下拥有状态、生命周期、策略选择或跨 phase 不变量。
- 实现必须在多个竞争性模块边界之间做选择。
- 预期 diff 无法解释为一个小 plan step，或没有清晰验证方式。

## 6. 最小抽象检查

新增或保留任何未经批准的非平凡抽象前，执行本检查。

优先使用能完成任务的最轻表示：

```text
已有 domain object / 容器
  > 更清晰的局部变量名
  > type alias
  > 局部 lambda
  > 函数局部 struct
  > `.cpp` / internal helper
  > private nested type 或 private method
  > internal class
  > public class/API
```

新增抽象至少满足以下一项才允许：

- 通过构造入口或方法维护真实不变量。
- 隐藏稳定、内聚的规则、协议细节、状态或策略。
- 具备独立生命周期、ownership 或失败语义。
- 被多个稳定调用点复用，并实质减少重复逻辑或组合错误。
- 降低调用方必须理解的知识，而不是把内部拼装规则外移。
- 形成可独立测试或演进的深边界。

以下抽象默认拒绝或暂缓：

- 只给局部中间结果换名。
- 只包装 map/vector/set/domain object，却不增加不变量或行为。
- 以 `Payload`、`Context`、`Row`、`Result` 或 `View` 形式在 helper 间搬运字段。
- 把固定调用顺序固化到 header/private API。
- 需要长注释解释其存在意义。
- 把 solver index、状态指针、领域对象和输出约束混进跨层临时结构。

必要时对候选类型记录简表：

```text
新增抽象：
解决的问题：
不变量/生命周期/ownership：
为何现有表示不足：
最低必要可见性：
决策：新增 / 局部化 / 暂缓 / 拒绝
```

## 7. Diff 审计

编辑后、最终回复前，审计实际 diff。

检查：

- 每个修改文件和修改符号是否都能映射到当前 plan step？
- 是否改变了 public API、private header API、签名、数据契约或调用方责任？
- 新增 helper/type 是否限于批准清单或第 6 节决策？
- helper 提取是在隐藏复杂性，还是暴露固定执行脚本？
- diff 是否引入风险边界外的行为变化？
- 测试或验证是否覆盖相关契约？
- 是否混入无关清理、格式化、命名或注释修改，导致 diff 扩大？

若发现漂移，应把实现修回 guardrail 内，或停止并报告需要新的设计/批准。

## 8. 输出要求

非平凡实现前，给出简短守门声明：

```text
实现 plan step：
允许：
不允许：
停止条件：
验证：
```

实现后输出：

- 已实现的 active plan step。
- API/抽象变更；若没有，明确写“无”。
- 新增 helper/type 决策，以及为何仍在 guardrail 内。
- 行为变化；若不应有，明确写“无意图行为变化”。
- Diff 审计结果。
- 已运行的验证及结果；若未运行，说明原因。

## 9. 自检

结束前确认：

- 实现遵循了已知设计来源或最小前置审计。
- 编辑前已声明 active plan step。
- 没有新增未批准的 public/private API surface。
- 没有新增未批准的 type、wrapper、context、payload、row、result 或 view。
- private header surface 没有累积临时实现细节。
- 行为、顺序、错误、副作用、生命周期和 ownership 没有越过声明的风险边界。
- 最终 diff 审计检查的是实际修改，而不是实现意图。
