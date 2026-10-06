# 2026-10-03 全项目复审

审查对象为 `d151573`（R12）加当前工作树中的上一轮修复。本文是第二轮审查，新增确认 **22 项：P1 4 项、P2 17 项、P3 1 项**。这些发现的源码修复已完成，状态及验证边界见 [修复记录](PROJECT_FIXES_2026-10-05.md)；上一轮已完成的修复和 R11/HidHide 判断见 [第一轮报告](/workspace/FH-DualSense-Enhanced/docs/REVIEW_2026-10-03.md)。原始审查阶段只新增审查文档，复现使用临时目录和模拟设备，没有执行真实游戏文件修改、驱动操作或发布。

P1 表示应优先处理的数据覆盖或发布通道错误；P2 表示有明确条件的功能、恢复或一致性错误；P3 表示发行说明问题。没有发现已证实的 P0。审查不能证明项目不存在其他缺陷。

## P1：优先处理

### 1. 游戏部分更新后，图标修复会覆盖新版原件

位置：[controller_icons.py:303](/workspace/FH-DualSense-Enhanced/src/modules/forzahorizon/controller_icons.py:303)。

已安装图标 MOD 后，若游戏更新只替换两个目标文件中的一个，代码进入 `partial` 分支，把两份文件都恢复为旧 manifest 的原件，再把 `current_hashes` 直接设为旧哈希。新版原件因此在备份刷新之前被覆盖。该状态会在界面启用安装/修复和还原操作，不需要并发。

复现：原件 `old-0/old-1` → 安装 MOD → 游戏把第一个文件更新为 `new-0` → 再安装并还原，最终得到 `old-0/old-1`，新版 `new-0` 没有被保存。直接还原同样缺少当前内容与备份版本的兼容性检查。

建议：每个目标分别识别 MOD、对应原件和未知新版本；遇到新版本先保存并验证，不能先用旧 manifest 覆写。对混合版本应停止操作并给出可恢复方案。

### 2. 两个实例安装图标时，可能把 MOD 记录为原件

位置：[controller_icons.py:219](/workspace/FH-DualSense-Enhanced/src/modules/forzahorizon/controller_icons.py:219)、[controller_icons.py:315](/workspace/FH-DualSense-Enhanced/src/modules/forzahorizon/controller_icons.py:315)。

安装的检查、备份和替换之间没有跨进程互斥。实例 B 在读取原件哈希后暂停，A 完成安装，随后 B 的 `_write_backup()` 读取的已经是 MOD；它仍通过自洽校验，提交 `original_sha256=[MOD, MOD]`，覆盖当前 manifest。之后还原报告成功，但实际仍是 MOD。

已用可控线程交错复现相同文件事务顺序。原始 generation 文件可能还在，但自动还原所依赖的 manifest 已不再指向它，不能宣称原件一定物理消失。

建议：按规范化游戏根目录对完整事务加跨进程锁，备份时同时校验安装开始时预期的原件哈希。此问题与第 1 项根因独立。

### 3. 多实例保存会覆盖另一个 Profile

位置：[preferences.py:639](/workspace/FH-DualSense-Enhanced/src/modules/config/preferences.py:639)。

`save(s)` 从磁盘读取最新 `active_profile`，却把调用实例的 Settings 写进去。A 仍使用 Default，B 保存并切换至 Track 后，A 仅修改全局语言也会把 Default 的调校写进 Track。这不要求两个写入同时发生；原子重命名和单纯文件锁都不能解决实例配置身份错配。

复现：B 的 Track `brake_max_force=9`，A 的 Default 为 `2`；A 保存语言后，Track 变成 `2`。

建议：保存时使用实例明确持有的 Profile 身份或版本，区分全局设置与 Profile 保存；检测外部修改后处理冲突。上一轮“删除当前 Profile 后同步替代配置”的修复不覆盖此路径。

### 4. preview 可能被错误发布到稳定通道

位置：[release.yml:61](/workspace/FH-DualSense-Enhanced/.github/workflows/release.yml:61)。

提交标题的 stable 正则优先于手动 channel，且没有限制 `release` 的词边界。两条实际工作流脚本复现均输出 `tag=R12; prerelease=false`：

- `workflow_dispatch(channel=preview)`，HEAD 标题为 `release R12`。
- 推送 `dev`，提交标题为 `prerelease R12`，其中的 `release R12` 被子串匹配。

这会把预期的预览构建送到稳定版 Release，可能更新稳定资产。复现只执行了提取出的 Parse trigger 脚本，没有调用 GitHub 发布。

建议：先处理显式手动通道，再处理自动 tag/提交标题；对稳定版触发词设置明确边界，并为上述输入建立行为测试。

## P2：前端与配置

### 5. 原始设备序列号会使 TUI 控件构造失败

位置：[system_tab.py:389](/workspace/FH-DualSense-Enhanced/src/modules/tui/system_tab.py:389)。

TUI 把原始 HID serial 直接拼成 Textual ID。蓝牙格式 `00:11:22:33:44:55` 会抛 `BadIdentifier`；USB/BT 两条接口使用相同序列号时还会产生重复 ID。设备枚举来自 `_raw_dualsense_interfaces()`，没有复用 native 的身份规范化和去重。

已复现冒号序列号构造异常；重复接口的 Textual 挂载也会拒绝重复 ID。建议使用合法且唯一的控件 ID 到规范化设备身份的映射，按物理设备去重，避免增加第二个 HID 读取者。

### 6. 取消托盘退出后，再最小化可能无法恢复窗口

位置：[tray.py:60](/workspace/FH-DualSense-Enhanced/src/modules/gui/tray.py:60)。

托盘 Quit 先停止 icon，再排队执行可被取消的关闭流程。用户在保存 Default 的命名提示中取消时，程序继续运行，`_started` 仍为 True。下一次最小化时 `start()` 返回成功，却没有重建已经停止的托盘，GUI 随后隐藏。

模拟 icon 已确认“停止后再次 start 返回 True，但没有创建新 icon”。建议在关闭获得最终确认后停止托盘，或取消时完整恢复其生命周期状态。

### 7. 旧 loop 的异步退出通知能关闭新会话

位置：[gui/main.py:765](/workspace/FH-DualSense-Enhanced/src/modules/gui/main.py:765)、[tui/main.py:318](/workspace/FH-DualSense-Enhanced/src/modules/tui/main.py:318)。

后台自然结束或异常退出时发布的回调/Message 不携带会话标识。若 UI 消费通知前已经完成后端重建，新 loop 使用清空后的同一个 `_stop`，旧通知就会关闭新会话。GUI/TUI 都已用延迟消费通知复现。

这是上一轮改为异步退出通知后遗漏的竞态。建议每次启动生成 generation，退出通知携带 generation，只有与当前会话一致才关闭；单独检查复用的 Event 不足以辨别旧通知。

### 8. TUI 过期的图标扫描结果会指向错误平台目录

位置：[fh6_utilities_tab.py:515](/workspace/FH-DualSense-Enhanced/src/modules/tui/fh6_utilities_tab.py:515)。

Steam 图标目录扫描开始后切换 Xbox App，旧异步结果仍会写入 `_icon_platform`、inspection 和路径框。随后 Install 使用旧 Steam 根目录，尽管当前设置已是 Xbox App。该路径缺少语言扫描及 GUI 对应逻辑已有的上下文核验。

已阻塞 discovery、切换平台再放行结果，并确认安装函数收到旧 Steam 路径。建议扫描带 request serial 和平台/路径快照，应用结果及执行写操作时再次验证。

### 9. 非 UTF-8 偏好文件绕过损坏恢复流程

位置：[preferences.py:314](/workspace/FH-DualSense-Enhanced/src/modules/config/preferences.py:314)。

`read_text(encoding="utf-8")` 的 `UnicodeDecodeError` 不属于当前捕获的 `OSError`；调用者用于启动恢复的 `PreferencesError` 包装因此失效。含非法字节的偏好文件会直接导致配置加载异常，而不是进入备份/重置流程。

已对临时偏好写入非法 UTF-8 并复现。建议将解码错误转换为 `PreferencesError`，保留原始字节供恢复备份。

### 10. 按安装目录检查进程时只检查第一个同名进程

位置：[game_launch.py:631](/workspace/FH-DualSense-Enhanced/src/modules/forzahorizon/game_launch.py:631)。

`find_game_process()` 返回第一个名字匹配项，`is_forza_game_running()` 才比较安装路径。若系统同时存在来自 A、B 两个目录的同名 FH6 进程，先枚举 A 时，对 B 的检查会返回 False，即使 B 仍在运行。依赖这个结果的语言文件操作可能误判游戏已关闭。

已用包含两个目录进程的枚举结果复现；真实双安装游戏并行场景未验证。建议在遍历中同时匹配名字和目标路径，检查所有候选项。

## P2：更新与恢复

### 11. 等待旧进程退出后，执行的新文件没有再次校验

位置：[update_helper.py:820](/workspace/FH-DualSense-Enhanced/packaging/windows/update_helper.py:820)。

Helper 在等待旧 PID 前验证 staged 哈希，等待结束后直接 `staged.replace(new)` 并 `Popen(new)`。等待期间 staged 若被另一个实例下载或本地文件操作替换，执行的字节就不再对应事务哈希。隔离复现捕获到 `Popen` 收到替换后的未验证内容；健康失败后的回滚保护不能撤销已经执行的内容。

这是本地并发/完整性边界问题，没有证据证明远程利用或权限提升，因此按 P2 记录。建议事务独占 staged，等待结束后重新校验，执行前再核对最终文件；同时缩小校验与使用之间的可变窗口。

### 12. 后台更新检查取消已下载更新的 READY 状态

位置：[service.py:109](/workspace/FH-DualSense-Enhanced/src/modules/update/service.py:109)。

启动时 `_load_pending()` 恢复已校验缓存为 READY，默认约 10 秒后的后台检查发现同一 release，却无条件设为 AVAILABLE。`auto_download_updates` 默认关闭，因此安装按钮消失，用户被要求重新下载。

已复现 `READY → AVAILABLE`，文件仍存在，但 `install_on_exit()` 报 `no verified update is ready`。建议同一已验证 release 保持 READY，网络检查状态与已有可安装缓存分别表示。

### 13. 快捷方式扫描/读取失败被当作迁移完整

位置：[shortcut_links.py:247](/workspace/FH-DualSense-Enhanced/packaging/windows/shortcut_links.py:247)、[shortcut_links.py:319](/workspace/FH-DualSense-Enhanced/packaging/windows/shortcut_links.py:319)。

Python 3.13 的 `Path.rglob()` 会吞掉目录扫描中的 `PermissionError`，外围 try/except 无法检测不完整枚举。已枚举到的 `.lnk` 若在 Load 或读取 target 时失败，`matched` 仍为 False，异常同样不进入 failed。两条路径都会使 helper 误以为旧版快捷方式已处理完，随后清理旧 EXE，留下断链入口。

已用真实不可读临时目录复现遗漏，并以抛 `PermissionError` 的 Shell Link 适配器复现返回 `([], [])`。Windows COM/ACL 全链路尚未实测。建议显式报告遍历错误，把“目标未知”与“确认无关”分开；未知结果不能授权清理旧文件。

### 14. 回滚可能遗漏外层已退出的子进程

位置：[update_helper.py:502](/workspace/FH-DualSense-Enhanced/packaging/windows/update_helper.py:502)。

`_stop_process()` 看到外层 Popen 已退出便返回 True，跳过后代处理。PyInstaller one-file 的外层退出而内层仍活着时，内层可能继续持有 EXE、HID 或 UDP，影响回滚。真实 Python 父子进程复现得到 `stop_reports_success=True`，但 child 仍存活。

当前删除/哈希保护通常会保留未完成 journal，不能据此宣称回滚会虚假提交。建议从启动时管理整个进程树，例如 Windows Job Object；父进程退出后再按父 PID 查找不足以保证回收。

## P2：输入、效果与触觉

### 15. HidHide 旧版 allowlist 迁移失败会丢失规则所有权

位置：[hidhide.py:733](/workspace/FH-DualSense-Enhanced/src/modules/dualsense/hidhide.py:733)。

`_prepare_legacy()` 先把 ownership journal 从旧 EXE 路径改成新路径，再写驱动白名单。驱动写失败时旧规则仍在，但 journal 已不记得它；随后 stop 可以返回 DISABLED 并清空 journal，留下本应由 FHDS 清理的旧 allowlist。

已有 fake HidHide API 加一次写失败已复现。启动前 prepare 成功常会避免该路径，但 prepare 失败后的自动重试仍可进入。建议先记录旧、新所有权并集作为意图，驱动写入并回读成功后再提交新集合，失败保留旧所有权。

### 16. PCM 高频副分量在音频块边界失去相位连续性

位置：[pcm.py:71](/workspace/FH-DualSense-Enhanced/src/modules/haptics/pcm.py:71)。

`sin(high_phase * 1.618)` 复用了每块结束按 `2π` 回绕的基础相位。1.618 不是整数倍，基础相位回绕会改变副分量相位，导致恒定输入的结果依赖分块方式。

关闭平滑差异后，对比一次长块与两个短块：48 kHz/512 和 3 kHz/32 都出现约 0.405 的最大样本差异；USB 边界参考值 `0.39648 → 0.41172`，分块结果为 `0.39648 → 0.19708`。算法不连续已证实，实机触感影响未测试。

建议为副分量独立保存相位，并添加恒幅信号的分块不变性验证。

### 17. 共享碰撞检测的“无事件”被误当成“没有提供检测结果”

位置：[mixer.py:392](/workspace/FH-DualSense-Enhanced/src/modules/haptics/mixer.py:392)、[effects.py:455](/workspace/FH-DualSense-Enhanced/src/modules/forzahorizon/effects.py:455)。

loop 把共享 CollisionDetector 的结果传给两个 renderer，但 `None` 同时表示“本帧没有碰撞”和“应自行检测”。共享 detector 产生事件时，局部 detector 没有更新基线；下一帧共享结果为 None，局部 detector 从旧基线重新识别同一次加速度变化，重新触发碰撞。

输入 `accel_x=0 → 30 → 30` 时，共享事件只发生在 1.01 秒，但 mixer 的 `_collision_started` 在 1.02 秒再次刷新，破坏公共 cooldown 和包络时序。建议使用独立 sentinel 区分省略参数与明确的 None，或始终只在 loop 检测。

### 18. 切换 Profile 后，端点墙仍沿用启动时参数

位置：[effects.py:444](/workspace/FH-DualSense-Enhanced/src/modules/forzahorizon/effects.py:444)。

`Controller.wall` 只在构造时使用 `settings.wall_zones` 生成，而 Profile 可以更新这个字段。随后 L2 满刹车和启用端点墙的 R2 仍返回旧帧，直到重建 Controller。

复现从 2 切换到 7 个区域后，当前 Controller 输出仍为 2 区，新建 Controller 输出为 7 区。建议检测参数变化后重建缓存，或按当前字段生成输出。

### 19. 分享码中的有限极大灯效频率会使遥测线程退出

位置：[lighting.py:108](/workspace/FH-DualSense-Enhanced/src/modules/forzahorizon/lighting.py:108)、[loop.py:313](/workspace/FH-DualSense-Enhanced/src/modules/loop.py:313)。

Profile 导入只校验类型和 finite，没有使用 UI 的范围限制。合法分享码里的 `tachometer_flash_rate_hz=1e308` 可以成功导入和应用；进入红线灯效时，`now * rate * 2` 溢出为 inf，`int(inf)` 抛 OverflowError。lighting 调用又没有像 trigger/mixer 一样隔离异常，导致整个 telemetry loop 退出。

已从分享码导入路径复现，属于异常配置输入触发，正常 UI 的 0..24 Hz 输入不会产生该值。建议在共享配置规范化层限定有效范围，并使单个灯效错误安全降级。

## P2/P3：启动与交付

### 20. P2：Windows 启动器丢失 CLI 参数的独立值

位置：[win_start.bat:43](/workspace/FH-DualSense-Enhanced/win_start.bat:43)。

参数解析只把 `--` 开头 token 放进 FLAGS，其他 token 全进入 GAME。例如 `--host 127.0.0.1 --port 5301` 会产生 FLAGS=`--host --port`，GAME=`127.0.0.1 5301`，导致错误启动包装命令且 argparse 缺值。`--host=127.0.0.1` 形式可绕开，但标准分离参数形式不可用。

依据脚本逐 token 路由和 main argparse 契约确认；本环境没有执行 cmd.exe。建议识别需要值的选项，或为 Steam 包装命令采用明确分隔符，保留引用与参数边界。

### 21. P2：Linux 冻结包在 Wayland 强制选择未打包的托盘后端

位置：[build_elf.sh:23](/workspace/FH-DualSense-Enhanced/packaging/linux/build_elf.sh:23)、[tray.py:21](/workspace/FH-DualSense-Enhanced/src/modules/gui/tray.py:21)。

构建脚本明确跳过 PyGObject/pycairo，依赖 xlib 后端；运行时检测到 Wayland 却强制 appindicator。锁定的 pystray appindicator 后端依赖 `gi`，干净冻结包不能满足，托盘启动失败。受限依赖环境下已复现 `No module named 'gi'`；没有构建实际 ELF 或测试桌面合成器。

建议统一构建与运行策略：若支持 AppIndicator 就完整打包所需 Python/native 依赖，否则不要自动选择该后端，并明确该环境的托盘可用性。

### 22. P3：预览版说明引用不存在的 Windows 文件名

位置：[release.yml:238](/workspace/FH-DualSense-Enhanced/.github/workflows/release.yml:238)。

Windows 构建始终生成 `FH-DualSense-Enhanced-R12.exe`，预览版说明却按 tag 展开成 `FH-DualSense-Enhanced-R12-preview.exe`；英文说明同样如此。Linux workflow 会按 tag 重命名，Windows 没有对应步骤。

建议保持 updater 所需的标准 EXE 命名，让发行说明读取真实 Windows asset 名称，避免用户寻找不存在的文件。

## 尚需实机证据的边界

- USB 校准报告：`motion.py:58` 对所有 41 字节 report 强制蓝牙 `0xA3` CRC，调用没有传 transport。Linux v6.12 `hid-playstation.c` 的 `ps_get_report()` 只在 Bluetooth 检查 CRC，而 DualSense USB 请求同样为 41 字节。静态规则不一致已核对，但没有真实 USB feature report，暂不计入上述确认数量。应采集 USB/BT 各自报告，验证硬件校准是否被误退回名义比例。
- 第一轮记录的 `identify_pulse` 独立 HID handle 风险仍在；此次没有实机确认写竞争。R11 使用 HidHide 后恢复支持物理/虚拟双输入冲突，但不等同于第一轮发现的 R12 隔离门禁启动互锁。
- 冻结版实际升级/回滚、Windows COM 快捷方式、ViGEmBus/HidHide 和 USB/BT handover 均仍需目标平台验证。

## 覆盖与验证

本轮覆盖 GUI/TUI 各页面及生命周期、配置/Profile/启动、Forza 发现和文件工具、UDP/loop/红线/碰撞/灯效、HID/XInput/HidHide/USB/BT/DSX、更新服务/helper/快捷方式、启动器/打包/CI/资产契约。候选项经代码复核和最小复现筛选，没有把已排除的 IPv6 支持问题、未证实的资源泄漏或仅风格诊断列为缺陷。

- 当前完整套件：`uv run --project src --frozen pytest -q -rs`，**1012 passed, 2 skipped**；跳过项需要 Windows GUI 和 Win32 wait-handle。
- 文件/配置临时复现 **7 passed**，其中包括非法编码、跨实例 Profile 覆盖、完整/部分游戏更新、并发备份、进程过滤和分享码极值。完整更新后的直接还原只作为底层 API 证据，主要用户可达问题按第 1 项的部分更新报告。
- 前端复现确认 4 类路径；HidHide 写失败、PCM 分块、碰撞重触发、端点墙缓存、更新 staged 变更/快捷方式失败/子进程存活、READY 丢失及 release parser 均完成隔离验证。
- 现有定向测试分别为：文件与配置 101 passed；更新/事务/快捷方式/启动 104 passed、1 skipped；交付契约 35 passed。这些是全量套件的子集，不能累加为额外覆盖数量。
- 第一轮已完成基础 Ruff、compileall、锁文件、Bash 语法和 diff 检查。完整 Ruff 与 Pyrefly 仍有第一轮报告列出的基线诊断，本轮未宣称这些检查全部通过。
- 复现脚本保存在本次工作区 `/tmp/fhds_*review*.py`，供当前会话定位；本文的条件、位置和观测结果不依赖临时脚本永久保留。

建议处理顺序：先解决 1–4 的数据/发布问题，再解决更新事务与第 7 项回归，随后统一前端异步上下文、配置约束和触觉状态语义。修复后应针对每个已确认触发序列补充行为回归，再进行 Windows 冻结版与实体手柄验证。
