# DmsTrack 深模块重构评审示例

## 1. 案例目的

本例展示如何对状态密集模块应用深模块视角。它不是通用跟踪算法规范，也不要求其他项目复用 DmsTrack 的业务规则。

主 skill 应先选择适合目标模块的复杂性镜头。只有遇到类似的状态密集算法 pipeline 时，才需要采用本例中的 owner、生命周期、匹配和发布分析。

## 2. 背景摘要

`DmsTrack` 对外主要提供 `Init()` 和 `Update()`。内部同时维护 face、body、hand 轨迹，核心更新函数混合了：

- 检测过滤与候选构造
- loss、ROI、anchor 和 gate
- 匈牙利匹配
- 卡尔曼预测与校正
- hit/miss 生命周期
- identity 和 owner 判断
- sanitize、legacy map 发布与日志

## 3. 模块边界判断

外部 API 较窄，调用方不需要逐步执行检测匹配、生命周期或输出发布。主要复杂性仍被封装在 `DmsTrack` 内部，因此外部边界总体属于深模块。

问题不在于 public API 过多，而在于内部编排与底层机制混在少数大函数中。

结论：

- 保留 `DmsTrack` 作为状态 owner。
- 不把 `FaceTracker`、`BodyTracker`、`HandTracker` 作为第一步 public-facing 拆分。
- 先改善内部组织，不扩大调用方责任。

## 4. 状态与不变量

该案例评审时先识别：

- identity 由 face track id 持有。
- body 和 hand 绑定到 owner identity。
- driver identity 由稳定 face track 选择。
- left/right hand 具有独立槽位，但输出 key 继承 owner。
- 生命周期、匹配顺序和输出 map 语义必须保持。

这些是案例中的项目事实，不是所有跟踪模块的通用规则。

## 5. 推荐的内部拆分

保留主流程中的领域顺序：

```text
Update
  -> update face tracks
  -> select driver identity
  -> publish face tracks
  -> update body evidence
  -> update hand evidence
```

优先提取内部机制：

- pure helper：loss、ROI、anchor、gate、几何判断。
- assignment helper：cost matrix、dummy assignment、匹配结果解析。
- lifecycle helper：hit、miss、expired。
- 类型专用状态更新：face/body/hand detection hit。
- owner context 和 hand slot 引用等小结构体。
- sanitize 与 publish 的明确副作用边界。

## 6. 不应机械统一的部分

- Face、Body、Hand 的 motion model 和 detection update 语义不同。
- Body 的 owner 优先顺序可能是算法策略，不应为复用 Hungarian 而改变。
- Hand first pass 与 second pass 的权限和候选范围不同。
- 生命周期推进次数和发布失败副作用必须逐项核对。

因此，通用 lifecycle 机制可以复用，但类型策略应继续分开表达。

## 7. 风险分类示例

### 低风险

- 提取检测分类、loss 和 gate pure helper。
- 引入局部 match result 结构体。
- 按原语句顺序提取 private helper。
- 合并重复的同 owner left/right 发布代码。

### 中风险

- 统一 dummy assignment 构造。
- 拆分 sanitize 和 publish 的副作用。
- 统一 first/second pass 的 slot hit 更新。

### 高风险

- 将顺序贪心改成全局匹配。
- 改变 owner 优先级或 fallback 权限。
- 改变 hit/miss 推进和删除时机。
- 改变 track id、legacy output key 或 public API。

## 8. 分阶段方案

1. 固化每帧输入和四类输出 map 基线。
2. 提取 pure helper，不改变语句顺序。
3. 提取各类型专用状态更新 helper。
4. 先瘦身 face/body 编排，再拆 hand 阶段。
5. 在回归测试保护下统一 assignment 基础设施。
6. 只有文件仍难以导航时，才考虑拆内部实现文件。

## 9. 示例结论的使用边界

可复用的是评审方法：

- 先看 API 深浅。
- 根据模块类型选择分析镜头；本例需要 owner、生命周期和不变量。
- 保留领域主流程。
- 抽内部机制。
- 标注行为风险。

不可直接泛化的是 DmsTrack 的 identity、owner、匹配顺序和输出 map 规则。其他模块必须从自身代码和契约恢复这些事实。
