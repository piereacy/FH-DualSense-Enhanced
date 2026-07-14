# FH-DualSense-Enhanced R2 发布设计

## 状态

- 日期：2026-07-14
- 分支：`feat/r2-trigger-dynamics`
- 状态：用户已批准，等待实施
- 发布边界：先完成本地修改、测试和构建；合并、推送、tag 与公开 Release 必须再次取得用户确认

## 目标

把已经完成实现与硬件验证的 Enhanced R2 准备为可发布版本，同时把冗长的上游衍生版本号迁移为独立的 `R` 版本体系。R2 继续提供 ZUV 兼容渠道，不在本轮移除旧启动器或自动更新。

## 版本身份

所有用户可见表面统一使用：

- 产品版本：`R2`；
- Git tag：`R2`；
- GitHub Release 标题：`FH-DualSense-Enhanced R2`；
- Windows 文件：`FH-DualSense-Enhanced-R2.exe`；
- Linux 文件：`FH-DualSense-Enhanced-R2`；
- GUI/TUI 版本文本：`R2`。

`src/pyproject.toml` 的 `[project].version` 使用 PEP 440 合法值 `2`，只服务于 uv、Python metadata、PyInstaller VERSIONINFO 和 ZUV build metadata。程序的显示层与打包层必须通过一个明确规则把内部 `2` 映射为公开 `R2`，不能重新显示 `v2`、`2.0` 或 `1.6.2.post2`。

## 版本体系迁移说明

README、发行说明和 GitHub Release body 必须明确说明：

- R2 开始采用 FH-DualSense-Enhanced 自己的 `R` 版本体系，以减少冗长并避免被误认为上游官方版本；
- 本项目基于 `Forza-Horizon-DualSense-Python 1.6.2`；
- 本项目参考 `HorizonHaptics 1.3.0`，对应参考仓库 tag `v1.3.0`；
- 历史 Enhanced R1 使用 `1.6.2.post1`，迁移后不再把上游版本嵌入当前产品版本。

基础版本与参考版本属于来源说明，不属于 R2 产品版本的一部分。

## ZUV 与启动器

R2 继续发布固定文件名 `FH-DualSense-Enhanced.zuv.py`，保留：

- `win_start.bat`；
- `linux_start.sh`；
- `uv` 管理的 Python 与依赖环境；
- GitHub latest Release 资产检查；
- 手动下载 ZUV 后放在启动器旁的网络故障备用流程；
- `--prerelease` 更新渠道。

保留固定 ZUV 文件名是兼容要求：已有 R1 启动器会继续访问 latest Release 的同名资产。R2 不讨论移除 ZUV；是否弃用或删除留给 R3 单独设计。

独立 EXE 仍是 Windows 推荐下载方式：它不需要 BAT、ZUV、uv 或系统 Python，但不自动更新。

## Release workflow

`.github/workflows/release.yml` 必须支持：

1. tag `R2` 触发稳定 Release；
2. 提交标题 `release R2` 触发稳定 Release；
3. 历史 `vX.Y.Z` / `vX.Y.Z.postN` tag 与 release commit 继续兼容；
4. 手动 `workflow_dispatch` 从当前内部版本 `2` 生成可移动的 `R2-preview` 预发布；
5. `R2-preview` 的标题为 `FH-DualSense-Enhanced R2 Preview`，并继续供 ZUV `--prerelease` 查找；
6. 稳定 R2 的标题只能是 `FH-DualSense-Enhanced R2`。

`workflow_dispatch` 默认生成 preview，并提供显式 `stable` 频道作为 tag/main push 事件未被仓库交付时的恢复入口。该入口仍使用相同构建 job、稳定 tag 与 Release 资产，不允许绕过构建门禁。

所有 job 继续生成 bundle、Windows EXE 和 Linux ELF。产物名称直接使用 workflow 得到的公开 tag，不能把内部 `2` 或旧 `v1.6.2.post1` 泄漏到文件名。

Release body 必须把 R2 新功能放在首位，同时保留安装、ZUV、Standalone、Data Out、防火墙和 Linux udev 说明。

## README 与发行文档

根 `README.md` 的中文、英文、日语同页内容必须同步。兼容文档 `docs/ReadmeEN.md`、`docs/ReadmeJA.md` 与 `packaging/release/README.txt` 也必须更新，避免版本和来源说明漂移。

R2 更新内容至少包含：

- telemetry-driven dynamic wheelspin；
- 铺装、积水、泥土与碎石 R2 扳机键材质频带；
- 时间型 asymmetric EWMA、hysteresis 与低速 raw wheel rotation；
- wheelspin 高于 rev limiter 的 R2 扳机键优先级；
- GT7 风格 L2 扳机键 ABS wall；
- 默认折叠的实验性设置；
- USB/Bluetooth synthetic 手感验证；
- Bluetooth 真实 Forza Data Out 的 wheelspin、低速 rotation、ABS 与四种材质验证。

DSX 没有专项适配或实机验证。文档可以说明现有 fallback 仍保留，但不能承诺完整 zoned wall，也不能把 DSX 写成 R2 发布门槛。

许可、原作者署名、原项目链接、Sponsor 在 About/License 中的位置和 `docs/THIRD_PARTY_NOTICES.md` 均保持不变。GitHub 自动生成的 Source code ZIP/TAR.GZ 继续作为源码发行，不额外制作手工源码包。

## 版本实现边界

用户可见的 `R2` 与内部 `2` 必须有自动测试覆盖，至少锁定：

- GUI/TUI 显示 `R2`；
- README 三语与兼容文档显示 `R2`；
- package metadata 为 `2`；
- workflow 识别 `R2`、`release R2` 和 `R2-preview`；
- Windows/Linux 产物名使用 `R2`；
- ZUV 文件名保持不变；
- 来源说明同时包含上游 `1.6.2` 与 HorizonHaptics `1.3.0`；
- 不再出现当前产品版本 `1.6.2.post1` 或标题 `Enhanced R1`，历史迁移说明中的引用除外。

不要修改 DualSense HID report、Forza packet parser、body haptics mixer、trigger 算法或默认参数。发布准备只改变版本身份、发行文档、workflow、打包命名和相应测试。

## 本地验证门槛

公开操作前必须在本地完成：

1. 版本身份与发行契约定向 pytest；
2. 全量 `uv run --project src pytest -q`；
3. `uv run --project src python -m compileall -q src/modules src/lang`；
4. `git diff --check`；
5. 使用 `packaging/zuv/build_zuv.bat piereacy/FH-DualSense-Enhanced` 构建 update-enabled ZUV；
6. 使用 `uvx zuv inspect` 确认内部版本 `2`、入口、volume 和 update repo；
7. 使用 `packaging/windows/build_exe.bat` 构建 Windows EXE；
8. 检查 EXE 名称为 `FH-DualSense-Enhanced-R2.exe`；
9. 检查 Windows VERSIONINFO、应用图标和 `--help` 启动冒烟。

当前 Windows 环境不声称已验证 Linux ELF；Linux build 必须由 GitHub Actions 或 Linux 环境执行。

任一本地测试或构建失败都必须停止。不得因为发布准备顺手改变业务算法，也不得在未取得用户再次确认时合并 `main`、push、创建 tag 或发布 Release。

## 完成条件

本地修改、测试与 Windows/ZUV 构建全部通过后，向用户提供：

- 变更摘要；
- 测试结果；
- ZUV 与 EXE 的绝对路径；
- EXE 版本、图标和启动冒烟结果；
- Linux 尚待 CI 的明确说明；
- 当前 Git 分支与工作区状态。

用户确认后才进入合并、push、tag `R2` 和公开 GitHub Release。
