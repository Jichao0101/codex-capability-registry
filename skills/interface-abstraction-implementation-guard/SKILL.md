---
name: interface-abstraction-implementation-guard
description: 用于非机械代码修改的实现阶段，约束 public/private API、内部抽象、helper 拆分、新增类型、模块边界、行为契约和重构 plan step，确保实现不偏离最近的 deep-module-design-review 结论或用户批准方案。若没有评审结论但任务明显涉及接口或抽象变动，本 skill 只执行最小前置审计，并在实现后要求 diff 审计。不要用于纯格式化、拼写、单行平凡修复、依赖版本更新、生成文件刷新，或用户明确禁止设计/抽象检查的实现任务。
---

# 接口与抽象实现守门

## 1. 执行边界

本 skill 只约束实现阶段，不重新做大范围模块设计评审。

若存在近期评审结论，把它视为设计事实源：

- 提取允许项、禁止项、风险边界、plan step、验证策略和停止条件。
- 只实现当前 active plan step 或明确批准的子集。
- 除非实现中命中停止条件，否则不重新打开大设计问题。

若没有评审结论，但实现明显触及接口或抽象边界，只执行第 3 节的最小前置审计。若审计发现非局部设计风险，应停止并建议先执行 `deep-module-design-review`。

## 2. 实现流程

### 第一步：查找设计事实源

编辑前按以下顺序寻找最近适用来源：

1. 当前对话中用户提供的实现方案。
2. repo、issue、PR 或任务记录中近期的 `deep-module-design-review` 结论或评审工件。
3. 说明当前契约的模块文档、设计记录、测试或代码注释。
4. 第 3 节的最小前置审计。

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
- 把 private header 中的方法和类型也视为维护者必须理解的 API surface；它们是成本项，需要用可读性、依赖显式性、phase 边界或不变量收益证明，但不是禁止项。
- 新增持久类型前，优先复用已有 domain object、容器、局部变量、局部 lambda、函数局部 struct 或 `.cpp`/internal helper。
- 只有当新类型已在批准清单中，或通过第 4 节最小抽象检查时，才允许新增。
- helper 提取优先保持 phase-level 语义；避免把固定顺序执行链暴露成一组 step helper。
- 低可见性不等于更好抽象。不得为了避免 private API surface 而把稳定 phase 边界强行压缩成函数局部 lambda。
- 局部 lambda 只适合局部机制；若 lambda 表达完整 phase、捕获大量状态、形成固定执行链、承载跨步骤状态演化，或导致不同抽象层级继续堆叠在同一大函数内，应停止并重新评估是否需要 phase-level `.cpp` / internal helper 或 private helper。
- 可读性优先级高于 private interface 最小化：若 `.cpp` helper 或局部机制仍让主流程难读、依赖隐式、phase 边界不清，允许新增 private helper/type；但必须记录它降低了哪些阅读复杂度，以及为何低可见性方案不足。
- 不新增只用于把数据从一步搬到下一步的 wrapper。
- 不用注释、测试或命名为缺少不变量、生命周期、稳定职责或复用价值的抽象做事后辩护。
- 除非当前 step 授权，否则不改变行为、失败模型、执行顺序、状态 ownership 或副作用。

如果实现中发现 guardrail 外的新需求，先停止，不要继续编码该部分。记录偏差，并请求用户批准或对新增点执行最小前置审计。

## 3. 无评审结论时的最小前置审计

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

## 4. 最小抽象检查

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

优先使用最轻表示，但不得以牺牲主流程可读性、依赖显式性和 phase 边界清晰度为代价。private interface 最小化低于可读性目标：若最轻表示只能把复杂 phase 留在原大函数内，或让不同层次的代码继续混杂，应升级候选可见性并重新评估 `.cpp` / internal helper、private helper 或更完整的 phase-level 边界。

新增抽象至少满足以下一项才允许：

- 通过构造入口或方法维护真实不变量。
- 隐藏稳定、内聚的规则、协议细节、状态或策略。
- 具备独立生命周期、ownership 或失败语义。
- 被多个稳定调用点复用，并实质减少重复逻辑或组合错误。
- 降低调用方必须理解的知识，而不是把内部拼装规则外移。
- 降低维护者阅读主流程时必须同时加载的层级数量，即使代价是增加少量 private interface。
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
可读性收益是否大于 private interface 成本：
决策：新增 / 局部化 / 暂缓 / 拒绝
```

## 5. Stale-Code Elimination Pass

每次实现后、Diff 审计前，必须执行 stale-code elimination pass。清理不是可选整理，而是实现阶段的强制闭环。

原则：

- Surgical change 包含删除本次修改使其过时的代码。
- 凡是被本次修改替代、绕过、降级、重复表达或失去唯一职责的代码，默认删除。
- 保留需要证明；不能证明仍有独立职责、调用路径、测试价值或兼容约束的旧实现，不应留在 diff 后。
- 不用注释、命名或测试夹具为已经退化的代码制造存在理由。
- 不扩大到无关历史债务；只处理本次修改造成或暴露的 stale code。

必须检查：

- 旧路径、旧分支、fallback、feature flag 分支是否仍可达且仍表达真实行为差异？
- 旧 helper、wrapper、adapter、临时类型是否只是在重复新路径或搬运同一数据？
- 旧变量、中间状态、缓存字段、参数、返回值是否仍有唯一职责？
- 注释、文档、日志、错误信息是否还在描述被替换的流程或不变量？
- 测试夹具、mock、golden、fixture、helper assertion 是否仍覆盖有效契约，而不是只服务旧结构？
- 新旧实现是否同时存在但只有一个是事实源？

保留任何疑似 stale code 时，必须记录简短理由：

```text
保留对象：
为何未 stale：
仍覆盖的调用路径/契约：
删除风险：
后续清理触发条件：
```

若发现 stale code，应优先删除或合并后再进入 Diff 审计。若删除会越过当前 guardrail，例如影响未批准的 public API、兼容承诺或外部契约，应停止并报告需要批准，而不是静默保留。

## 6. Diff 审计

编辑后、最终回复前，审计实际 diff。

检查：

- 每个修改文件和修改符号是否都能映射到当前 plan step？
- 是否改变了 public API、private header API、签名、数据契约或调用方责任？
- 新增 helper/type 是否限于批准清单或第 4 节决策？
- 若新增 private helper/type，diff 是否明确换来了主流程可读性、依赖显式性或 phase 边界收益，而不是只把代码搬家？
- helper 提取是在隐藏复杂性，还是暴露固定执行脚本？
- diff 是否引入风险边界外的行为变化？
- 测试或验证是否覆盖相关契约？
- 是否混入无关清理、格式化、命名或注释修改，导致 diff 扩大？
- 是否已完成第 5 节 stale-code elimination pass；保留的疑似 stale code 是否有明确证明？

若发现漂移，应把实现修回 guardrail 内，或停止并报告需要新的设计/批准。

## 7. 输出要求

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
- Stale-code elimination pass 结果；若保留疑似 stale code，给出保留理由。
- Diff 审计结果。
- 已运行的验证及结果；若未运行，说明原因。

## 8. 自检

结束前确认：

- 实现遵循了已知设计来源或最小前置审计。
- 编辑前已声明 active plan step。
- 没有新增未批准的 public/private API surface。
- 没有新增未批准的 type、wrapper、context、payload、row、result 或 view。
- private header surface 没有累积临时实现细节。
- 已删除或合并本次修改造成的旧路径、旧 helper、旧变量、旧分支、旧注释和旧测试夹具；任何保留都有明确理由。
- 行为、顺序、错误、副作用、生命周期和 ownership 没有越过声明的风险边界。
- 最终 diff 审计检查的是实际修改，而不是实现意图。
