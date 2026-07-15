# R4 前端、更新器与触觉扩展实施计划

日期：2026-07-16  
状态：执行中

## 1. 建立可回归基线

- 运行 R3 完整测试并保存结果。
- 为当前设置字段、GUI 页面绑定、DualSense USB/BT 报告和 0x36 PCM 添加缺失的特征测试。

## 2. 前端共享框架和三方案

- 新增 `gui/variants.py`，集中三套布局元数据。
- 将 `gui/main.py` 的 Header、导航和内容容器拆成可配置外壳，Tab 实例保持唯一。
- 新增总览页面与重新分类的导航入口。
- 更新初音未来主题令牌。
- 修改 PyInstaller spec 和构建脚本，输出三个方案 EXE。

## 3. 内置更新器

- 实现版本模型、GitHub Releases 客户端、下载校验、缓存和状态机。
- 将 GUI/TUI 更新设置从 ZUV 哨兵切换到内置更新服务。
- 实现 Windows Update Helper、替换、回滚和启动清理。
- 为离线、超时、错误哈希、资产不匹配和回滚添加测试。

## 4. 红线和新增触觉

- 修复红线饱和，新增占空比和起始冲击。
- 增加增压阻力、G 力阻力、碰撞扳机冲击、空闲扳机路面纹理。
- 复用现有碰撞检测信号，明确优先级。
- 同步 GUI、TUI、翻译、默认 Profile 和迁移。

## 5. 灯效和 Bluetooth 改进

- 增加传输无关的灯效状态与 RPM/挡位计算器。
- 扩展 0x02、0x31 和 0x36 状态字段，保持 CRC 和触发器字段。
- 增加 Bluetooth 软限幅、误差反馈量化和拥塞诊断。

## 6. 文档与验证

- 更新 README、老三样和 `docs/PROJECT_STATE.md`。
- 运行 `uv run --project src pytest -q`。
- 运行 `uv run --project src python -m compileall -q src tests`。
- 构建三个 EXE，并进行启动、页面、配置保存和更新器本地 Fixture 冒烟测试。
- 在 USB 和 Bluetooth 真机上验证扳机、握把、灯效及 0x36 连续输出。
- 最终只交付通过同一功能测试矩阵的三个 EXE。
