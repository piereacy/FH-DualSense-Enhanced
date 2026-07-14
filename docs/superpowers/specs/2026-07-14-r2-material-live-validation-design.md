# Enhanced R2 真实路面材质验证设计

## 状态

- 日期：2026-07-14
- 分支：`feat/r2-trigger-dynamics`
- 状态：用户已批准，等待执行
- 对象：R2 扳机键动态 wheelspin 的真实材质识别与手感

## 目标

在 Bluetooth DualSense 和真实 Forza Data Out 下，分别验证铺装路面、积水路面、泥土路面和碎石路面的 wheelspin 材质识别。每种材质必须同时具有遥测证据、正确的 R2 扳机键频带和用户手感确认。

## 范围

本轮只验证四种实际路面材质，不新增算法功能，不调节默认值，也不修改 transport：

- 使用当前 Bluetooth DualSense；USB 与 Bluetooth synthetic 手感已完成，不重复 USB 整套验证。
- 使用现有 `Controller.update()` 与当前 Profile 生成 L2/R2 扳机键帧。
- 关闭握把振动，只输出扳机帧，避免 body haptics 干扰判断。
- 不做前驱或后驱实机验证。`DRIVEN_WHEELS` 映射继续由现有自动测试保证，不作为 Enhanced R2 发布门槛。
- 不开发或验证 DSX。

## 监听架构

每种材质单独启动一次最长 120 秒的 trigger-only 实时监听器。监听器绑定 `127.0.0.1:5300`，加载当前 Profile，通过现有 `UDPListener` 解析 Forza Data Out，再调用现有 `Controller.update()` 生成扳机帧并写入当前 Bluetooth DualSense。

监听器仅在 wheelspin 超过当前阈值时记录材质事件。每个事件必须记录：

- `drive_train`；
- 主导驱动轮；
- 主导驱动轮的 longitudinal slip 或低速 raw rotation；
- `surface_rumble` 与 `wheel_in_puddle`；
- 算法选择的材质；
- 最终 R2 扳机键 frame、frequency 与 amplitude。

每段启动时使用新的 `Controller`，从而清空 EWMA、hysteresis、rev hold 与其他 transient state。每段结束或异常退出时必须把 L2/R2 扳机键归零并关闭 HID handle。

## 当前分类契约

材质只由 wheelspin 的主导驱动轮决定，不允许静止材质值或非驱动轮替代主信号：

1. `wheel_in_puddle > 0`：积水路面，频带 `80..150`。
2. 否则 `abs(surface_rumble) > 0.30`：碎石路面，频带 `12..30`。
3. 否则 `abs(surface_rumble) > 0.10`：泥土路面，频带 `30..70`。
4. 其余：铺装路面，频带 `90..180`。

频率在频带内随 EWMA wheelspin level 动态插值，不能把某个固定 frame 当作唯一正确输出。amplitude 仍由 wheelspin level、材质 scale 与 G-force damping 共同决定。

## 执行顺序

严格分四段执行，每段由 Codex 明确宣布开始，用户完成一次稳定 wheelspin 后停止驾驶并确认手感，随后才进入下一段：

1. 铺装路面；
2. 积水路面；
3. 泥土路面；
4. 碎石路面。

一段失败后立即停止，不继续混测后续材质。

## 通过标准

每种材质必须同时满足以下条件：

1. Forza Data Out 正在输出有效赛道遥测，wheelspin 信号超过当前进入阈值。
2. 日志中的主导驱动轮、puddle/rumble 数值和算法分类符合车辆所在实际路面。
3. R2 扳机键输出为动态 wheelspin frame，frequency 落入该材质的配置频带，而不是 rev-limiter `(30, 12)` 或普通 resistance frame。
4. 用户确认该材质的 R2 扳机键反馈合适，并能与此前已经确认的材质手感区分。
5. 松开油门或 wheelspin 结束后，反馈按现有 EWMA release 平滑退出，不遗留上一材质状态。

只有四段全部满足，才把“真实材质 signature”记为完成。synthetic frame 通过不能替代真实材质验证。

## 失败与异常处理

- 若实际路面与算法分类不一致，保存对应遥测值并停止该段。先用该真实数据增加失败回归，再讨论阈值或分类修改，不现场盲调。
- 若 `surface_rumble` 始终为 0，记录游戏振动设置与原始遥测；不要自动把所有路面视为铺装路面通过。
- 若 UDP 5300 被占用、Forza Data Out 断流、手柄断连或 packet size 不是 324 字节，该段作废。
- 任意异常路径都必须执行扳机归零和 HID handle 关闭。
- 日志能证明触发路径，但不能代替用户的手感确认。

## 验证后的处理

- 四段全部通过：更新 `docs/PROJECT_STATE.md`，复跑全量 pytest，并进入 Enhanced R2 合并与发布准备。
- 某段失败：只为真实失败数据建立回归测试和最小算法修复；修复后重新验证失败材质，不无条件重跑已通过材质。
- 本轮不因前驱/后驱或 DSX 未做实机验证而阻塞 Enhanced R2。
