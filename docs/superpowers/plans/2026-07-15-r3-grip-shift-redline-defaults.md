# Enhanced R3 握把换挡冲击与红线默认值实施计划

对应设计：`docs/superpowers/specs/2026-07-15-r3-grip-shift-redline-defaults-design.md`

目标是消除未公开的握把换挡冲击默认行为，提供独立普通设置，将握把红线改为默认关闭并加入 1.5 信号增益，最后把仓库准备到等待 Enhanced R3 Release 发布的状态。

## Task 1：用测试固定新默认值和 Profile 迁移

修改：

- `tests/test_community_defaults.py`
- `tests/test_haptic_settings.py`
- `src/modules/config/settings.py`
- `src/modules/config/preferences.py`

步骤：

1. 增加失败测试，断言 `Settings()` 中 `enable_grip_redline_haptics` 和 `enable_grip_gear_shift_haptics` 均为 `False`，并断言新增三个数值字段为设计默认值。
2. 增加命名 Profile 测试，覆盖 Enhanced R2、早期 Enhanced R3 preview、已有显式红线开关和已自定义新增字段。
3. 增加重复 `load()` 的幂等测试，确保用户值不被第二次迁移覆盖。
4. 在 `Settings` 增加字段并修改红线默认值。
5. 把 `grip_redline_gain` 加入 `_GRIP_REDLINE_FIELDS`；为握把换挡新增字段补默认值，但不从扳机字段复制。
6. 运行：

```powershell
uv run --project src pytest -q tests/test_community_defaults.py tests/test_haptic_settings.py
```

## Task 2：拆分握把换挡状态机

修改：

- `tests/haptics/test_mixer.py`
- `src/modules/haptics/mixer.py`

步骤：

1. 增加失败测试，证明默认换挡不再产生握把冲击。
2. 增加启用、速度门槛、正挡门槛、双侧低频、强度、持续时间、impact/master 缩放测试。
3. 增加扳机与握把开关/参数互不影响测试。
4. 增加运行中关闭立即清除，以及关闭期间仍更新 `_prev_gear`、重新开启不补发旧事件的测试。
5. 用 `enable_grip_gear_shift_haptics` 门控 `_shift_until`，改读独立强度和持续时间；每帧继续更新 `_prev_gear`。
6. 保留碰撞、悬挂、ABS、路面和 compatible rumble 路由不变。
7. 运行：

```powershell
uv run --project src pytest -q tests/haptics/test_mixer.py
```

## Task 3：实现握把红线 1.5 信号增益

修改：

- `tests/haptics/test_mixer.py`
- `src/modules/haptics/mixer.py`

步骤：

1. 调整测试 fixture，在需要红线事件的测试中显式启用握把红线，避免新默认值让测试意外失效。
2. 增加未饱和配置的 1.5 倍幅度测试。
3. 增加高强度配置最终限幅为 `1.0` 的测试。
4. 调整 USB/Bluetooth 测试，断言两种 transport 使用同一个增益后事件，并保留既有侧别投影。
5. 在基础幅度、engine intensity 和最终 master/duck 之间加入 `grip_redline_gain`，不增加 transport 特有系数。
6. 运行：

```powershell
uv run --project src pytest -q tests/haptics/test_mixer.py tests/haptics/test_frame.py
```

## Task 4：更新 GUI、TUI 和翻译

修改：

- `src/modules/gui/controls_tab.py`
- `src/modules/tui/controls_tab.py`
- `src/modules/gui/settings_tab.py`
- `src/modules/tui/settings_tab.py`
- `src/lang/de.py`
- `src/lang/ja.py`
- `src/lang/ru.py`
- `src/lang/tr.py`
- `src/lang/zh.py`
- `src/lang/zh_tw.py`
- `tests/test_haptic_settings.py`

步骤：

1. 先扩充 parity 和翻译测试，固定 `Grip feedback`、普通 `Grip gear-shift thump` 调校、重命名后的 `R2 trigger gear-shift thump` 和实验性 `Grip signal gain`。
2. GUI/TUI Controls 同步新增握把反馈分组和开关。
3. GUI/TUI 普通设置同步新增握把换挡强度/持续时间，并重命名原扳机分组。
4. GUI/TUI 实验性设置同步新增红线增益。
5. 补齐六个非英语语言模块；英语使用 key 本身，无需增加独立英语映射。
6. 运行：

```powershell
uv run --project src pytest -q tests/test_haptic_settings.py
```

## Task 5：更新长期文档和决策记录

修改或创建：

- `docs/DECISIONS.md`
- `docs/ARCHITECTURE.md`
- `AGENTS.md`
- `docs/PROJECT_STATE.md`

步骤：

1. 创建 `docs/DECISIONS.md`，记录原生游戏振动接管推迟、不能用单向 telemetry 忠实还原全部菜单/CG 振动、未来精确方案需要虚拟控制器桥接。
2. 记录隐藏握把换挡冲击源自 HorizonHaptics 参考实现，Enhanced R3 将其改为独立、默认关闭、普通设置。
3. 记录握把红线默认关闭及 1.5 信号增益，明确它不是感知强度保证。
4. 更新 `docs/ARCHITECTURE.md` 的 mixer、Settings、Profile 迁移和 UI 边界，只描述已实现代码。
5. 更新 `AGENTS.md`，定义“老三样”并要求硬件触觉验证记录游戏内振动和 Steam Input 状态。
6. 更新 `docs/PROJECT_STATE.md`，分开记录已实现、自动测试、构建和未执行硬件验证。

## Task 6：全量自动验证与自 review

运行：

```powershell
uv run --project src pytest -q
python -m compileall -q src/modules src/lang
git diff --check
git status --short --branch
git diff
```

自 review 清单：

1. 对照设计逐项核对默认值、迁移、mixer、UI、翻译和文档。
2. 检查所有新增设置是否为 Profile 字段，且未误入 `GLOBAL_FIELDS`。
3. 检查扳机 effect 与 HID report 未被修改。
4. 检查 USB/BT 没有分叉检测或强度规则。
5. 搜索 TODO、FIXME、占位符、新 em dash 和错误的独立 R2 术语。
6. 修复 review 发现的问题并重新运行受影响测试及全量测试。

## Task 7：构建并审计 Release 工件

运行 Windows 构建：

```powershell
packaging\windows\build_exe.bat
```

运行带更新仓库指向的 ZUV 构建：

```bat
set UPDATE_REPO=piereacy/FH-DualSense-Enhanced
packaging\zuv\build_zuv.bat
```

随后：

1. 核对 `src/pyproject.toml`、运行时版本、Windows version resource、README、workflow、EXE 名称和 ZUV 更新源均使用 Enhanced R3 语义。
2. 记录 EXE 和 ZUV 的绝对路径、大小、SHA-256 和构建时间。
3. 检查构建未把缓存、用户配置或无关产物加入 Git。
4. Linux 构建如当前 Windows 环境无法可靠执行，明确记录“未执行”及原因，不伪装为通过。
5. 硬件实车验证若本轮未由用户配合执行，明确记录“未执行”；不能用连接测试替代。
6. 提交实现与文档，确保工作树干净。
7. 停在等待发布阶段，不创建 tag、不推送 Release、不上传资产。
