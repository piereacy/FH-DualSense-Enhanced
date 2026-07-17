# 独立“关于与许可证”页面及界面中性命名设计

## 目标

将原本附着在“握把触觉”页面底部的署名与许可证信息迁移为独立页面，删除总览页没有实际功能的 R4 展示卡片，并统一清理已经停用的界面代号。项目正式名称始终为 `FH-DualSense-Enhanced`，现有青绿色主题、卡片布局和交互能力保持不变。

## 已确认方案

采用独立页面方案：

- GUI 左侧导航在“日志”下方新增“关于与许可证”，对应独立 `AboutTab`。
- TUI 在“日志”后新增同名独立页，继续与 GUI 提供相同的署名、原项目和 Sponsor 入口。
- “握把触觉”页面不再渲染关于卡片，也不再承担许可证入口职责。
- 总览页删除没有状态、设置或跳转功能的 R4 展示卡片，不用关于信息替换该位置。
- Sponsor 链接只在独立关于页出现，不放到总览页或常用设置页面。

## 页面内容与许可边界

关于页复用 `src/modules/about.py` 的 `APP_NAME`、`ATTRIBUTION`、`SOURCE_URL` 和 `SPONSOR_URL`，展示：

- 项目名称和当前 Enhanced 版本；
- 原作者署名；
- 原项目链接；
- Sponsor 链接。

链接继续通过现有安全 URL 打开入口处理。迁移不能删除 `LICENSE` 要求的署名、原项目和 Sponsor 信息，也不能改变 `docs/THIRD_PARTY_NOTICES.md` 中的第三方归属。

## 命名清理

当前工作树中，除“老三样” `AGENTS.md`、`docs/ARCHITECTURE.md`、`docs/DECISIONS.md` 用于记录内部设计来源外，停用的界面代号不得再出现。具体包括：

- 窗口标题改为纯 `FH-DualSense-Enhanced`；
- Windows `FileDescription` 改为中性的 Enhanced 项目描述；
- 删除总览卡片及各语言对应文案；
- 修正 `docs/PROJECT_STATE.md`、历史设计/计划文档和测试中的旧称；
- README、Release 正文和其他用户界面继续只使用 `FH-DualSense-Enhanced`。

不重写 Git 历史。老三样只把旧称记录为青绿色界面设计的内部来源，不得再将其定义为产品名称、窗口名称、构建变体或必须保留的用户可见字符串。

## 实现边界

- GUI 新增 `src/modules/gui/about_tab.py`，由 `src/modules/gui/main.py` 注册导航和页面。
- TUI 新增 `src/modules/tui/about_tab.py`，由 `src/modules/tui/main.py` 注册页签。
- 从 GUI/TUI `settings_tab.py` 删除专用于内嵌关于卡片的分支和控件；其他触觉设置不变。
- 不改变主题令牌、DPI、滚轮路由、设置持久化、更新器、遥测、扳机或握把触觉行为。
- 不增加新的联网请求；用户点击 Source 或 Sponsor 后才调用现有浏览器打开逻辑。

## 验证

- 更新 GUI/TUI 页面结构测试，确认关于入口位于日志之后、触觉页不再包含关于内容、总览页不再包含装饰卡片。
- 更新分发契约测试，确认当前文件中停用代号只存在于老三样。
- 检查所有语言都能显示“关于与许可证”，缺失翻译时仍可回退英文。
- 运行 GUI/TUI 定向测试、完整 `pytest`、`compileall` 和 `git diff --check`。
- 重新构建 R4 Windows EXE，核对窗口标题、`FileDescription`、版本资源、SHA-256 和启动冒烟结果。
- 本轮不修改触觉算法，不要求重新进行 USB/Bluetooth 实机手感测试。
