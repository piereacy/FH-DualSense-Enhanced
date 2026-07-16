# Enhanced R4 单一 Console、配置持久化与关键交互实现计划

日期：2026-07-17

依据：`docs/superpowers/specs/2026-07-16-r4-console-persistence-interactions-design.md`

## 目标

将 Enhanced R4 收敛为单一 Miku Console EXE，修复 DPI 窗口内卡片裁切和鼠标滚轮失效，建立持久化 Default、出厂恢复、首次语言检测、统一退出保存提醒和更新导航白点，并保持命名 Profile、分享码、触觉与 HID 行为兼容。

## 实施顺序

### 1. 先建立配置和语言契约测试

修改或新增：

- `tests/test_haptic_settings.py`
- `tests/test_community_defaults.py`
- 新增 `tests/test_system_language.py`
- 新增 `tests/test_profile_session.py`

覆盖：

- Default 跨连续 `load()` 保留修改。
- 首次配置采用系统显示语言，已有配置不被覆盖。
- 简体、繁体、日语、德语、俄语、土耳其语和未知语言映射。
- 完整恢复保留命名 Profile、重建 Default/globals 并切回 Default。
- 严格写入失败不更新运行中 Settings。
- ProfileSession 只对本次 Default 的 Profile 字段变化返回提醒。

### 2. 实现配置底层

修改或新增：

- 新增 `src/modules/config/system_language.py`
- 新增 `src/modules/config/profile_session.py`
- 修改 `src/modules/config/preferences.py`
- 修改 `src/modules/config/profiles.py`
- 修改 `src/modules/config/__init__.py`

实现：

- Windows UI language 检测和 locale 后备。
- 删除启动时覆盖 Default 的行为。
- 让 `_write()`、`save()` 和 Profile mutation 返回明确结果。
- 增加完整出厂恢复、备份和原子提交。
- 增加 `profile1` 起始的下一个可用名称生成。
- 保存命名 Profile 成功后才返回名称。

运行第 1 步测试，确认旧迁移、分享码和 named Profile round-trip 同时通过。

### 3. 先建立关闭、恢复和更新提示的纯逻辑测试

修改或新增：

- `tests/gui/test_window_behavior.py`
- 新增 `tests/gui/test_close_flow.py`
- 扩展 `tests/test_updater.py`

覆盖：

- 五种正常退出请求进入统一协调器。
- 无修改直接退出。
- 保存、直接退出和取消三条分支。
- 保存失败不退出。
- 更新 Helper 只在退出决策通过后启动。
- UpdateSnapshot 到导航白点可见性的纯函数。

### 4. 实现 GUI 关闭协调、保存弹窗和恢复入口

修改或新增：

- 新增 `src/modules/gui/dialogs.py`
- 修改 `src/modules/gui/main.py`
- 修改 `src/modules/gui/system_tab.py`
- 修改 `src/modules/gui/overview_tab.py`
- 修改 `src/modules/gui/profiles_tab.py`
- 修改 `src/modules/gui/settings_tab.py`
- 修改 `src/modules/update/presentation.py`

实现：

- `request_close(reason, before_exit=None)` 和单一 `_perform_quit()`。
- 隐藏到托盘时先恢复窗口再显示模态弹窗。
- 输入框预填 `profileN`，保存严格成功后才退出。
- 更新安装延迟到关闭决策完成后。
- 三个“还原默认设置”入口调用同一 GUI 操作。
- 恢复成功刷新 Profile 和全部控件，提示重启后完全生效。
- System 导航白点按更新快照持续显示。

### 5. 先建立滚动和响应式布局测试

修改或新增：

- 新增 `tests/gui/test_scroll_routing.py`
- 扩展 `tests/gui/test_r4_frontend.py`

把方向归一化、候选顺序、边界转交和列数选择提取为可无显示环境测试的纯函数。覆盖 Windows、Linux、内外层边界和宽窄阈值。

### 6. 实现滚轮路由和页面溢出修复

修改：

- `src/modules/gui/widgets.py`
- `src/modules/gui/controls_tab.py`
- 必要时修改 `overview_tab.py`、`profiles_tab.py`、`lang_tab.py`、`logs_tab.py`

实现：

- 根窗口统一 MouseWheel/Button-4/Button-5 路由。
- FastScroll 注册、销毁注销、指针命中和内外层边界转交。
- Driving 页标题下使用 FastScroll。
- 卡片自然高度，不再使用固定高度 row weight。
- 根据内容宽度在两列和单列之间重新排布同一组卡片。
- 审计其余页面的可见高度和 scrollregion。

### 7. 先更新单一 EXE 和更新器资产契约测试

修改：

- `tests/test_updater.py`
- `tests/test_enhanced_distribution.py`
- `tests/test_packaging_haptics.py`
- `tests/gui/test_r4_frontend.py`
- `tests/test_about_and_release.py`

覆盖：

- 唯一资产 `FH-DualSense-Enhanced-R<n>.exe` 和 `.sha256`。
- 更新器拒绝旧三方案资产。
- 源码不再需要 variant 参数和环境变量。
- spec/build/workflow 只生成一个主 EXE。

### 8. 删除 Stage/Studio 并收敛生产路径

修改或删除：

- 删除 `src/modules/gui/variants.py`
- 修改 `src/modules/gui/main.py`
- 修改 `src/modules/tui/main.py`
- 修改 `src/modules/update/github.py`
- 修改 `src/modules/update/service.py`
- 修改 `packaging/windows/fhds.spec`
- 修改 `packaging/windows/build_exe.bat`
- 修改 `.github/workflows/release.yml`
- 修改 `.gitignore` 中只服务于多方案构建的规则

实现单一标题、单一文件名、单一更新资产和单次 PyInstaller 构建。保留 Helper、许可证、第三方声明和回滚边界。

### 9. 翻译与文档

修改：

- `src/lang/zh.py`、`zh_tw.py`、`ja.py`、`de.py`、`ru.py`、`tr.py`
- `README.md`
- `docs/ReadmeEN.md`
- `docs/ReadmeJA.md`
- `AGENTS.md`
- `docs/ARCHITECTURE.md`
- `docs/DECISIONS.md`
- `docs/PROJECT_STATE.md`

同步单一 Console、Default 持久化、出厂恢复、首次语言、退出提醒、滚轮和更新白点。历史三方案决策标为已被单一 Console 决策取代。Release body 保留中文说明并只列一个 EXE。

### 10. 验证与交付

依次执行：

1. 所有新增定向测试。
2. `uv run --project src pytest -q`。
3. `python -m compileall -q src/modules src/lang`。
4. `git diff --check`。
5. `packaging\windows\build_exe.bat`。
6. 核对唯一 EXE、`.sha256`、版本资源和内置 Helper。
7. 启动 EXE，手动验证所有长页面滚轮和底部开关可见。
8. 调整窗口宽高验证两列/单列响应。
9. 手动验证恢复默认三个入口和退出保存三种选择。
10. 模拟更新状态验证白点。
11. 检查 crash log、残留进程和 Git 工作区。

真实 Forza 手感不属于本次 UI/配置修改的必要验证。若未连接游戏，本次记录游戏内振动和 Steam Input 为“未参与”。
