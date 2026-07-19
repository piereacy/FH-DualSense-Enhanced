# Enhanced R6 Xbox App XInput 桥实施计划

日期：2026-07-19
状态：核心实现、完整测试和 Windows 构建完成，冻结界面与发布验收中

对应规格：`docs/superpowers/specs/2026-07-19-r6-xbox-app-xinput-bridge-design.md`

## 1. 保存基线并审计重叠改动

- 记录 `git status --short --branch`、最近提交和完整未提交文件列表。
- 运行 XInput 改动前的完整 `uv run --project src pytest -q`，把既有失败与本功能回归分开。
- 阅读当前未提交的 `settings.py`、`preferences.py`、`gui/main.py`、`gui/overview_tab.py`、翻译、打包脚本和相关测试，增量修改，不覆盖 FH4/FH5/FH6 启动与 FH6 语言摘要工作。
- 不清理、reset、stash 或提交用户无关改动；需要提交时只暂存本计划或能够明确归属的文件/区块。

## 2. 固定第三方资产和供应链契约

- 将固定 x64 `ViGEmClient.dll` 放入项目 Windows 运行资产目录，记录 `130,048` 字节和 SHA-256 `2BF0CB1D809039573C922737D298A1653D4DBC61408060FF45A9BCFDE82E97D2`。
- 将官方 `ViGEmBus_1.22.0_x64_x86_arm64.exe` 放入 Windows 安装资产目录，记录 `6,278,576` 字节和 SHA-256 `89220A7865076B342892F98865F3499FB7C4CFD673159E89D352C360FD014C6A`。
- 新增资产哈希契约测试，防止打包输入被静默替换。
- 修改 `packaging/windows/fhds.spec`，只在 Windows one-file EXE 中携带 DLL、installer 和许可证资产；Linux 构建不包含它们。

## 3. 先实现纯 DualSense 输入解析器

- 从真实 USB/Bluetooth HID 报告和公开协议实现 `src/modules/dualsense/input_state.py`，不复制 DS4Windows GPL 源码。
- 定义不可变输入状态、D-pad 枚举、标准按钮集合和明确的 parse error。
- 为 USB、Bluetooth 分别添加最小有效长度、report ID、按钮、八向 D-pad、摇杆、L2/R2 和截断/非法值测试。
- 添加 DualSense 到 `XUSB_REPORT` 的纯映射测试，覆盖中心、端点、Y 轴方向、Guide 和无 deadzone/平滑边界。
- 运行解析器定向测试，确认所有协议事实都由字节级 fixture 固定。

## 4. 实现最小 ViGEmClient ABI 层

- 新增 `src/modules/xinput/` 包和 `vigem_client.py`，只声明规格允许的 client、X360 target 和 update API。
- 固定 `ctypes.Structure` 字段宽度、packing、函数参数和返回错误码，不导入 `vgamepad` runtime。
- 以 fake DLL/function table 测试 alloc/connect/add/update/remove/free 正常顺序、每个失败点和重复清理幂等性。
- 在当前机器现有 ViGEmBus `1.21.442.0` 上创建合成 target，并用系统 `XInputGetState` 反向验证注入状态；不升级或卸载现有 driver。

## 5. 实现 latest-state bridge worker 和卡键保护

- 新增 `bridge.py`，实现不可变 snapshot、状态机、latest slot 和单 worker 所有权。
- fake clock 覆盖 `100 ms` 中立化、`3 s` target 移除、输入恢复重建和退出清理顺序。
- 验证生产速度高于消费速度时只应用最新状态，不形成队列。
- 验证 ViGEm update 失败只关闭 bridge，不向调用方线程抛出未处理异常。
- 不注册 rumble callback，不实现 game-native vibration 路径。

## 6. 接入现有 DualSense I/O 和应用生命周期

- 为 `DualSense` 增加可热切换的非阻塞 input consumer，不引入第二个 HID reader。
- Xbox App 模式下使用 USB 约 `1 ms`、Bluetooth 约 `4 ms` 的输入轮询上限；Steam 模式保留当前空闲等待。
- 保持 trigger、灯效、compatible rumble 和 Bluetooth `0x36` 输出的现有串行所有权、CRC 和调度。
- 在主程序 backend 生命周期中创建 bridge service；平台切换和退出按中立、target remove、client free 顺序停止。
- 添加回归测试，证明无 consumer 时旧输出行为不变，bridge 错误不停止 haptics backend。

## 7. 实现离线 ViGEmBus 检测和显式安装

- 新增 `driver.py`，先以 client connect 能力判断 driver 是否可用，不按版本号强制升级。
- 对内置 installer 执行固定 SHA-256 和 cache-only `WinVerifyTrust`；任一失败都拒绝执行。
- 用户确认后通过 `ShellExecuteW(..., "runas", ...)` 触发 UAC；取消、成功、reboot-required 和失败 code 映射到规格状态。
- 成功退出后重新连接 bus；仍不可用时进入 `RESTART_REQUIRED`，不重复弹 UAC。
- 使用 mock 覆盖 driver 缺失、UAC 取消、签名失败和 installer 失败；当前电脑不执行升级或卸载。

## 8. 增加平台配置和状态界面

- 在 `Settings` 和 `preferences.GLOBAL_FIELDS` 增加 `preferred_forza_platform`，默认 `steam`，允许 `steam`/`xbox_app`。
- 保证旧配置迁移、Default 持久化、恢复出厂设置、named Profile 和 share code 边界正确。
- 在总览增加 Steam/Xbox App 选择及 bridge 状态；Xbox App 模式不调用 Steam URI，优先以 `Get-StartApps` 返回的 AUMID 激活已安装包，未发现时打开对应 `msxbox://game/?productId=<id>` 产品页。
- GUI 只在 Tk 主线程轮询不可变 snapshot；TUI/headless 复用同一字段和 service，不从日志猜状态。
- 补齐所有语言模块的必要键或明确英文回退，并增加 GUI/TUI 字段契约测试。

## 9. 更新许可证、长期文档和用户文档

- 更新 `docs/THIRD_PARTY_NOTICES.md` 和 GUI/TUI 关于页，加入 ViGEmClient MIT、vgamepad MIT、ViGEmBus BSD-3-Clause、版本、项目链接和 EOL 事实。
- 更新老三样，明确实际模块、数据流、HidHide 非依赖、driver 不自动更新、Xbox 360 target 和体积实测。
- 功能实现状态、测试、构建和待验证项同步到 `docs/PROJECT_STATE.md`。
- README 只增加用户必须知道的平台选择、关闭游戏内振动、Steam/Xbox App 使用边界和 driver 首次安装，不展开内部 ABI。
- 后续 Release body 继续使用完整中文与英文，并明确真实 Xbox App 游戏是否已经验证。

## 10. 完整验证、构建和硬件验收

- 运行 XInput 定向测试、完整 `uv run --project src pytest -q`、`python -m compileall -q src/modules src/lang` 和 `git diff --check`。
- 构建 Windows one-file EXE，校验 `.sha256`、版本资源、内置资产哈希、启动、退出和平台切换。
- 报告最终 EXE 精确大小、相对线上 R5 的 MiB/百分比增量、冷/温启动和 Steam/Xbox App 模式空闲 CPU；超过 `52 MiB` 立即暂停并重新确认。
- USB 和 Bluetooth 分别验证 Windows XInput 反读、100 ms 中立保护、3 s target 移除和现有触觉回归。
- 选择 Xbox App 模式，关闭 Steam Input 和 Forza 游戏内振动，使用 Steam 版 Forza 完成实车控制验收；切回 Steam 后验证虚拟 target 消失并恢复 Steam Input。
- 没有 clean-machine driver 安装或 Xbox App 游戏实测时明确记录“未执行”，不把兼容推断写成已验证。

## 11. 实施范围修订

用户在核心 XInput 设计确认后追加了 Xbox App 启动入口与 FH6 DualSense 图标 MOD。本计划第 8 步原先的“只提示手动启动”已由显式 AUMID/product-ID 启动链路替代；不在范围仍包括 Xbox 安装路径自动发现、商店管理和直接执行游戏 EXE。图标 MOD 使用独立事务模块、应用内作者鸣谢和第三方声明，具体状态以 `docs/PROJECT_STATE.md` 为准。
