# Enhanced R3 握把换挡冲击与红线默认值设计

## 背景

当前 `src/modules/haptics/mixer.py` 会在车辆速度高于 `3 km/h` 且正挡挡位发生变化时，向左右握把加入固定 `0.8` 的低频瞬态。该行为源自项目早期参考的 HorizonHaptics 设计，但目前没有独立开关，强度被硬编码，并复用 R2 扳机键的 `gear_shift_duration_ms`。因此，即使用户关闭了 R2 扳机键换挡冲击，握把仍会产生一次未在界面中说明的换挡冲击。

Enhanced R3 当前还默认开启握把红线振动，默认幅度为 `192/255`。实车体验表明红线脉冲可以辨认，但应作为可选效果默认关闭；用户启用后，希望其信号强度相对当前实现提高 50%。

## 目标

1. 保留握把换挡冲击，但改为默认关闭、可独立启用的普通功能。
2. 为握把换挡冲击提供独立强度和持续时间，不再复用任何 R2 扳机键换挡参数。
3. 握把红线振动默认关闭。
4. 为握把红线增加默认 `1.5` 的信号增益，并继续使用最终安全限幅。
5. 保持 USB 与 Bluetooth 使用同一个 `HapticFrame` 事件语义，不为传输方式设置不同强度。
6. 保存已有命名 Profile，并为缺失新字段的 Profile 进行幂等迁移。

## 非目标

- 不接管或复现 Forza/Steam Input 的原生游戏振动。
- 不修改碰撞检测、碰撞包络、路面连续反馈或抓地力路由。
- 不修改 R2 扳机键换挡冲击的检测、优先级、频率、强度或持续时间。
- 不新增 DSX 握把触觉支持。
- 不创建 Enhanced R3 tag 或 GitHub Release；本轮只准备达到可发布状态的工件和证据。

## 配置模型

在 `src/modules/config/settings.py` 增加以下 Profile 级字段：

```python
enable_grip_gear_shift_haptics: bool = False
grip_gear_shift_strength: float = 0.8
grip_gear_shift_duration_ms: float = 100.0
grip_redline_gain: float = 1.5
```

并把现有字段默认值改为：

```python
enable_grip_redline_haptics: bool = False
```

这些字段不加入 `preferences.GLOBAL_FIELDS`，因此随 Profile 保存、导出和导入。`grip_gear_shift_strength` 表示进入握把 mixer 前的归一化瞬态强度，界面范围为 `0.0..2.0`；`grip_gear_shift_duration_ms` 的界面范围为 `0.0..2000.0`。`grip_redline_gain` 的界面范围为 `0.0..2.0`，属于实验性调校参数。

## 握把换挡冲击数据流

`HapticMixer` 每帧都更新 `_prev_gear`，无论握把换挡开关是否开启。这样运行中开启功能时只会响应下一次真实挡位变化，不会根据旧挡位制造补发事件。

只有同时满足以下条件时才开始握把换挡冲击：

- `enable_grip_gear_shift_haptics` 为真；
- 上一挡和当前挡均大于零；
- 挡位发生变化；
- 车辆速度大于 `3 km/h`。

事件截止时间使用 `grip_gear_shift_duration_ms`，左右低频通道均加入：

```text
grip_gear_shift_strength × impact_haptics_intensity
```

最终仍由 `body_haptics_intensity` 缩放并由 `HapticFrame` 限幅。Bluetooth 继续经过既有 compatible rumble 下混，USB 继续输出四通道 frame。两种传输方式共享检测、持续时间和归一化强度。

运行中关闭 `enable_grip_gear_shift_haptics` 时，mixer 必须立即把 `_shift_until` 清零，不允许已开始的冲击继续到原截止时间。该开关不读取 `enable_gear_shift` 或 `enable_gear_shift_brake`，R2 扳机键换挡逻辑也不读取任何新增握把字段。

## 握把红线增益

红线事件的高频基础幅度改为：

```text
(grip_redline_amp / 255) × grip_redline_gain × engine_haptics_intensity
```

低频分量继续乘以 `grip_redline_low_ratio`。该事件随后沿用现有 redline/collision duck、`body_haptics_intensity` 和最终 `clamp01()`。不能在乘增益前把 `grip_redline_amp / 255` 以外的完整表达式提前限幅，否则默认 `1.5` 在存在输出余量时无法产生真实的 50% 信号提升。

`1.5` 表示信号域乘数，不承诺人体感知严格增强 50%。当最终混音超过 `1.0` 时允许按现有安全规则削顶。USB 与 Bluetooth 必须从同一个已增益事件生成输出，Bluetooth 不使用额外补偿系数。

## 界面

### Controls

GUI 和 TUI 的 Controls 页新增普通分组 `Grip feedback`，包含：

- `enable_grip_gear_shift_haptics`：`Grip gear-shift thump`

该分组不放入实验性区域。现有 `Redline feedback` 分组保留握把红线总开关和左右握把选择；由于默认值变化，首次使用新 Default Profile 时该开关显示为关闭。

### Settings

GUI 和 TUI 的普通 `SETTING_SECTIONS` 新增 `Grip gear-shift thump`：

- `grip_gear_shift_strength`：`Grip thump strength`
- `grip_gear_shift_duration_ms`：`Grip thump length (ms)`

现有 `Gear shift thump` 更名为 `R2 trigger gear-shift thump`，避免把扳机调校误认为握把调校。原字段和行为不变。

`grip_redline_gain` 放入默认折叠的 `EXPERIMENTAL_SECTIONS` 中现有握把红线高级调校区域，标签为 `Grip signal gain`。实验性区域已有“不建议自行调节”说明，无需新增第二套提示。

所有新增或更名文案同步到 `src/lang/de.py`、`ja.py`、`ru.py`、`tr.py`、`zh.py` 和 `zh_tw.py`。简体中文必须使用“R2 扳机键换挡冲击”和“握把换挡冲击”，避免与 Enhanced R2 版本混淆。

## 配置迁移

`Default` Profile 继续在每次启动时由最新 `Settings()` 重建，因此会自动获得：

- 握把红线关闭；
- 握把换挡冲击关闭；
- 握把换挡强度 `0.8`、持续时间 `100 ms`；
- 握把红线增益 `1.5`。

命名 Profile 的处理规则：

1. 已显式保存 `enable_grip_redline_haptics` 的 Profile 保留该值，不因新默认值变为关闭。
2. 早期 Enhanced R3 preview 仍按现有 `_migrate_r3_redline_split()` 规则恢复其红线开关和调校；新增 `grip_redline_gain` 仅补默认 `1.5`。
3. 缺少握把换挡字段的所有命名 Profile 补入默认关闭、`0.8` 和 `100 ms`，不得从 R2 扳机键字段推导。
4. 迁移重复执行不得改变已迁移或用户自定义值。
5. Profile 分享码继续依赖现有 dataclass 字段枚举自动携带非默认值，未知字段仍按现有规则忽略。

## 错误处理与运行时边界

- 缺失、无法转换或越界配置继续沿用 `_setting()`、`_apply_snap()` 和最终 `clamp01()` 的现有容错策略。
- `grip_gear_shift_duration_ms <= 0` 等价于不产生可观察持续事件。
- `grip_gear_shift_strength <= 0` 不产生可观察输出，但仍允许正常更新挡位状态。
- body haptics 或 telemetry 关闭时沿用现有静音和状态重置路径。
- 不改变 HID report flags、USB 音频布局、Bluetooth CRC 或 compatible rumble release 行为。

## 验证

自动测试至少覆盖：

1. `Settings()` 默认关闭握把红线和握把换挡冲击，新增数值默认正确。
2. 默认状态发生挡位变化时没有握把换挡输出。
3. 开启后只在有效正挡变化且速度门槛满足时产生双侧低频冲击。
4. 握把换挡强度、持续时间独立生效，并继续服从 impact/master 强度。
5. R2 扳机键换挡开关和参数不影响握把；握把开关和参数不影响扳机。
6. 运行中关闭握把换挡会立即清除事件；关闭期间持续更新挡位，重新开启不会补发旧事件。
7. 红线在未饱和配置下输出为原实现的 `1.5` 倍，在高强度配置下安全限幅为 `1.0`。
8. USB frame 与 Bluetooth compatible rumble 共享增益后的事件语义和既有侧别投影。
9. Default Profile 重建、Enhanced R2 Profile、早期 Enhanced R3 preview 和已自定义 Enhanced R3 Profile 的迁移均正确且幂等。
10. GUI/TUI 字段顺序、分组和开关保持一致，所有语言键完整，Profile/share-code round trip 通过。

完成定向测试后运行：

```powershell
uv run --project src pytest -q
python -m compileall -q src/modules src/lang
git diff --check
```

硬件验证必须分别记录 USB/Bluetooth 连接方式、Forza 游戏内振动开关和 Steam Input 状态。验证握把方向和本项目冲击时应先关闭游戏内振动，避免原生 rumble 掩盖结果。若本轮无法执行真实驾驶验证，必须明确写“未执行”，不能以启动脉冲或单元测试代替。

## 文档与发布边界

实现完成后更新：

- `docs/DECISIONS.md`：记录原生游戏振动接管推迟到 Enhanced R3 之后，以及握把换挡冲击的来源和默认关闭决策。
- `docs/ARCHITECTURE.md`：只写已经实现的 mixer、配置和 UI 边界。
- 根目录 `AGENTS.md`：定义“老三样”为 `AGENTS.md`、`docs/ARCHITECTURE.md`、`docs/DECISIONS.md`，并要求硬件测试记录游戏内振动和 Steam Input 状态。
- `docs/PROJECT_STATE.md`：记录代码、测试、构建、硬件验证和 Git 状态的事实层级。

Release 准备只在全量测试、compileall、diff 检查、版本/构建脚本/README 一致性审计通过后进行。允许构建本地 Enhanced R3 EXE 和 ZUV 工件并记录 SHA-256，但不创建 tag、不上传资产、不发布 GitHub Release，最终停在等待用户发布确认的阶段。
