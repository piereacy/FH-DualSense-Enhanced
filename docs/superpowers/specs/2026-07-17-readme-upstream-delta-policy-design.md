# README 上游差异说明规则设计

## 目标

为后续 README 建立稳定的比较口径，让普通用户能够直接判断 FH-DualSense-Enhanced 相比 `Forza-Horizon-DualSense-Python 1.6.2` 增加了什么，同时避免把整个 Enhanced 项目的累计增强与某一个 Release 的版本增量混写。

## 双层比较口径

- 三语 README 必须包含一个简短章节，说明当前 Enhanced 版本相比上游 `Forza-Horizon-DualSense-Python 1.6.2` 的累计核心增强。
- GitHub Release body 继续说明当前版本相比上一稳定 Enhanced 版本的本版新增，例如 Enhanced R4 相比 Enhanced R3。
- README 不使用“R4 新增”来描述 R1 到 R3 已经实现的能力；Release body 也不能把上游原本已有的能力写成本版新增。

## README 内容边界

- 累计增强控制在四到六个用户可感知类别，例如扳机、握把触觉、连接、配置、界面与更新。
- 每一类必须能由当前生产代码、自动测试或已经记录的真实硬件结果证明。
- 只写用户能够感知的结果，不写内部字段、HID offset、报文字节、线程、滤波参数或逐个设置开关。
- 未实现、仅设计、仅推测或尚未验证的效果不得写成已完成。
- 根英文 README、`docs/ReadmeZH.md` 和 `docs/ReadmeJA.md` 必须同步同一组事实。

## 老三样落点

- `AGENTS.md` 记录后续 Codex 修改 README 时必须遵守的操作规则和验证要求。
- `docs/ARCHITECTURE.md` 记录上游 `1.6.2` 是用户文档的能力对比基线，并解释累计差异与版本增量的边界。
- `docs/DECISIONS.md` 记录采用双层口径的产品决定、原因和后果。

本轮不直接改写 README 功能清单。老三样更新完成后，先基于当前代码分别整理“Enhanced R4 累计相比上游 1.6.2”和“Enhanced R4 相比 Enhanced R3”两份候选清单；与用户确认后再更新三语 README。

## 验证

- 检查老三样对比较基线、累计增强、版本增量和三语同步的表述一致。
- 检查没有把 `docs/PROJECT_STATE.md` 错算进“老三样”。
- 运行 `git diff --check`，确认只修改设计和老三样文档，没有改动 README 或业务代码。
