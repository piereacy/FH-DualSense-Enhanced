# 2026-10-08 继续审查修复

基线为已推送的 `2547513`。用户要求持续修复，并在源码审查没有新的明确问题时说明。本批修复以下已复现边界，不改手感默认值或协议字节。

## 已完成修复

- **UDP 转发**：阻塞 socket 和逐包主机名解析可能拖慢反馈。初始化解析 IPv4 目标，逐包非阻塞发送；下游拥塞只丢弃其副本。以实际绑定地址过滤解析后的自转发别名，独立忽略坏目标和转发 socket 创建失败。listener 初始化异常释放已绑定端口。包含真实 localhost 原始数据包收发验证。
- **HidHide 与体感**：清零 raw sensor 仍会经校准偏移产生 camera 输入，Deflection 历史角度也不会消失。内部 `motion_suppressed` 禁止激活与输入权恢复，重置 gyro 算法，恢复后重新建立基线。初始重力样本无效时允许后续有效样本建立参考。原校准、物理报告解析和唯一 HID owner 保持原有边界。
- **诊断导出**：同秒并发的检查后替换会覆盖另一实例 ZIP；轮转日志与 crash 日志的 `read_bytes()` 无读取上限。现在独占预留最终名称，独立临时 ZIP 完成后原子发布，失败清理自有文件。每个日志正文读取及导出最多 2 MiB，仅保留完整首尾记录并在脱敏扩张后再次限长，四份日志总计最多 8 MiB。不依赖硬链接，可用于 FAT/exFAT 便携目录。
- **取消自动退出**：游戏关闭或遥测超时后 loop 已退出，取消 Default 提示或保存失败仅留下窗口。现在 GUI/TUI 合并恢复请求，后台 helper 有界等待旧线程及生命周期锁，仅重新创建 telemetry worker，复用 backend/listener；generation 屏蔽迟到通知。界面不等待 helper。意外崩溃、锁/线程等待超时与启动失败保留明确错误，不反复自动重启。

## 验证

- 完整 `pytest -q -W error`：**1286 passed、3 skipped**，相比基线新增 47 项回归。
- Pyrefly：**0 errors、1 suppressed、147 warnings**；warning 未清零。
- Ruff 0.16.10 基础 E4/E7/E9/F 通过；同版本 HEAD 基线 384 项、本批 381 项，无新增诊断。工具版本与上一批不同，不直接比较旧版总数。
- 限定源码 compileall、`uv lock --check`、Linux shell 语法、源码 CLI `--help` 和 `git diff --check` 通过。

最后一轮对入口、反馈循环、退出提示和更新入口复核未发现其他明确中高影响新问题；这不替代真实系统验收。三个跳过项要求 Windows。真实冻结 EXE 更新、HidHide/ViGEmBus、DualSense USB/Bluetooth 和 Forza 游戏内联动均未执行。原有技术债继续保留于 `ARCHITECTURE.md`，本批不发布二进制或创建标签。
