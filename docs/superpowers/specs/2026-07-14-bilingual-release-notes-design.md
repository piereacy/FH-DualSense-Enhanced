# R1 与 R2 双语 Release 正文设计

## 状态

- 日期：2026-07-14
- 范围：GitHub Release `v1.6.2.post1` 与 `R2`，以及项目级发布规则
- 状态：用户已确认，等待实施

## 目标

为已发布的 Enhanced R1 和 Enhanced R2 增加完整中文说明，同时保留现有英文正文、Release 元数据、tag 和全部资产。将同样的双语要求写入根目录 `AGENTS.md`，使后续发布默认遵守。

## 正文结构

两个 Release 均采用以下顺序：

1. `## 中文说明`
2. 与该版本现有英文正文完整对应的中文内容
3. `## English`
4. 保留现有英文正文

不采用中英文逐节交错，也不使用折叠区。中文放在前面，确保中文用户打开 Release 页面即可直接阅读；英文保持连续，便于原有用户和搜索使用。

## R1 中文内容

R1 中文正文必须与现有 `v1.6.2.post1` Release 的事实一致，完整覆盖：

- 首个稳定 Enhanced 版本及上游 `1.6.2` 基础；
- 自适应刹车/油门扳机；
- 遥测驱动的发动机、路面、悬挂、碰撞、积水、轮胎打滑、wheelspin 与 ABS 握把触觉；
- USB/Bluetooth、静止怠速 gating、社区默认调校和后台选项；
- Windows launcher、手动 ZUV、独立 EXE 和 Linux 安装方式；
- Steam Input、Data Out `127.0.0.1:5300` 和防火墙要求；
- 原作者、原项目、HorizonHaptics 参考和许可证提示。

不得把 R2 的动态 wheelspin、GT7 风格 ABS wall 或 `R` 版本体系写入 R1 功能。

## R2 中文内容

R2 中文正文必须与现有 `R2` Release 的事实一致，完整覆盖：

- R2 扳机键动态 wheelspin、驱动轮滑移、低速轮速、非对称 EWMA、迟滞、G 力阻尼与四种材质频带；
- wheelspin 高于 rev limiter 的优先级；
- L2 扳机键 GT7 风格 ABS wall；
- 已有自适应扳机和握把触觉、USB/Bluetooth 差异与实验性设置；
- 独立 `R` 版本体系、上游 `1.6.2`、HorizonHaptics `1.3.0` 和历史 R1 `1.6.2.post1`；
- Windows/Linux launcher、手动 ZUV、独立二进制、Data Out、防火墙、Linux udev 和 prerelease 频道。

术语遵守项目规则：版本写 `Enhanced R2`，手柄按键写 `R2 扳机键`。

## AGENTS.md 规则

在“修改原则和限制”中增加稳定规则：所有公开 GitHub Release 正文必须提供完整中文说明，并保留英文内容；修改历史 Release 时不得删除任一语言。发布前必须核对中文和英文所述功能、安装方式、版本、资产名称及验证状态一致。

## 实施边界与验证

- 只修改 `AGENTS.md`、本设计文档和两个 GitHub Release 的 body。
- 不修改业务代码、workflow、tag、Release 标题、draft/prerelease 状态或资产。
- 使用临时正文文件调用 `gh release edit --notes-file`，避免命令行转义损坏 Markdown；临时文件不提交。
- 更新后分别读取两个 Release，核对 `## 中文说明`、`## English`、关键版本/资产文本和原有英文内容。
- 执行 `git diff --check` 和 `git status --short --branch`；提交 `AGENTS.md` 后推送 `main`。
