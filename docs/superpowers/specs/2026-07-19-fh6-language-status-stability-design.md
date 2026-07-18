# FH6 语言状态语义与稳定刷新设计

日期：2026-07-19
状态：用户已确认后端优先范围；前端接入延后到 R6 后续需求收齐后

## 1. 问题与目标

“FH6 中文文字 + 英文语音”页面当前存在两个问题：

1. 页面把 Steam manifest 中的原始 token `english` 显示为“Steam 语言：english”，容易被理解为 Steam 客户端界面语言。实际数据表示 FH6 在 Steam 中选择的游戏内容语言。
2. 页面每五秒扫描一次状态。每次扫描开始时都会暂时显示“正在扫描 FH6”，并对操作按钮执行 `pack_forget()` 后重新 `pack()`，导致稳定状态下的卡片周期性闪烁和布局抖动。

最终目标是始终明确区分 FH6 的基础游戏语言、当前实际文字语言和语音语言，并使周期扫描不改变稳定页面的布局。修复只能读取状态，不得触碰或再次交换任何游戏文件。

## 2. 本轮范围

用户选择后端优先方案 A。本轮只打通纯底层语言摘要能力：

- 根据 `LanguageInspection` 计算当前 FH6 游戏使用语言、实际显示语言和语音语言。
- 返回稳定、未本地化的数据，不依赖 GUI、TUI 或翻译 catalog。
- 增加覆盖主路径和异常路径的自动测试。
- 不修改 `src/modules/gui/`、`src/modules/tui/` 或 `src/lang/`。
- 不修复当前五秒周期扫描的界面闪烁；该问题已定位，但与三行前端接入一起延后。

本轮 API 完成后，R6 前端可以直接消费，不需要重新推导语言状态。

## 3. 最终用户可见语义（延后）

后续 R6 前端接入时，GUI 和 TUI 始终显示以下三行：

- `当前 FH6 游戏使用语言：{language}`
- `实际显示语言：{language}`
- `语音语言：{language}`

`当前 FH6 游戏使用语言` 指 Steam 为 FH6 记录的游戏内容语言，不是 Steam 客户端界面语言。原始 token 必须本地化，例如 `english` 在简体中文界面中显示为“英语”，不得直接展示英文 token。

本功能只交换 `CHS.zip` 和 `EN.zip` 的文件名，两者均为 StringTables 文本包；它不修改语音资源。因此：

- 语音语言跟随 FH6 的 Steam 游戏内容语言。
- 实际显示语言由 Steam 游戏内容语言所加载的文本槽位与当前语言包内容共同决定。
- 无法从现有安全证据确认时显示“未知”，不得猜测。

## 4. 状态映射

当前已支持并需要确定展示的主路径如下：

| Steam FH6 游戏语言 | 文件状态 | 当前 FH6 游戏使用语言 | 实际显示语言 | 语音语言 |
| --- | --- | --- | --- | --- |
| `english` | `NATIVE` | 英语 | 英语 | 英语 |
| `english` | `SWAPPED` | 英语 | 中文 | 英语 |
| `english` | `RECOVERY_REQUIRED`、`MISSING`、`UNKNOWN`、`CORRUPT` | 英语 | 未知 | 英语 |
| 未知 | 任意 | 未知 | 未知 | 未知 |
| 非英语 | `NATIVE` 或其他 | 对应的本地化语言或原始值 | 未知 | 对应的本地化语言或未知 |

非英语状态继续遵守现有安全门禁，不能启用中文文字与英文语音交换。当前设计不扩大支持语言范围，也不声称能够识别所有 FH6 语言包。

## 5. 底层语言摘要模型

`src/modules/forzahorizon/fh6_language.py` 增加不可变的 `FH6LanguageSummary`：

- `game_language`
- `display_language`
- `voice_language`

`game_language` 和 `voice_language` 保存规范化后的 Steam token，例如 `english`；未知时为空字符串。`display_language` 使用现有 `ArchiveLanguage`，仅返回 `ENGLISH`、`CHINESE` 或 `UNKNOWN`，不把损坏的文件状态误写成一种显示语言。

纯函数 `summarize_fh6_languages(inspection)` 根据 `LanguageInspection`、`FH6LanguageState` 和 `FH6Install.steam_language` 计算摘要。函数不得访问磁盘、Steam、GUI 或全局配置，也不得修改传入对象。后续展示层只负责本地化这些事实，GUI 和 TUI 不得分别复制映射逻辑。

## 6. 无抖动刷新（延后）

初次进入页面且尚无任何有效扫描结果时，可以显示“正在扫描 FH6”。已有稳定结果后：

- 五秒周期扫描保持上一次状态、详情和三行语言信息不变。
- 扫描期间只把危险操作临时设为 disabled，不隐藏操作按钮，不改变按钮文字，不重新排列控件。
- 扫描完成后原位更新发生变化的值。
- 操作按钮只有在安全动作从“存在”变为“不存在”或反向变化时才改变可见性；同一动作的普通刷新不得重复 `pack_forget()`/`pack()`。
- 用户显式点击“重新扫描”也不需要清空稳定结果；错误在扫描完成后按现有错误路径显示。

GUI 使用一个“已经取得扫描结果”的状态区分首次扫描与后台刷新。TUI 使用同一语义，避免每五秒把稳定标题改成“正在扫描 FH6”。本节不在本轮后端实现范围内。

## 7. 安全与错误边界

- 不修改 `CHS.zip`、`EN.zip`、Steam manifest、Steam 设置或用户配置。
- 不改变启用、还原、崩溃恢复、游戏运行检测和 Steam English 门禁。
- 扫描错误继续显示错误信息，但不能先清空稳定布局。
- 只有用户确认后的既有操作函数可以改名语言文件。
- 若 Steam token 与语言包状态无法形成受支持的组合，实际显示语言为“未知”。

## 8. 测试与验收

### 8.1 自动测试

- `english + NATIVE` 映射为 `english / ArchiveLanguage.ENGLISH / english`。
- `english + SWAPPED` 映射为 `english / ArchiveLanguage.CHINESE / english`。
- 英语基础语言下的损坏、缺失和恢复状态保留 `english` 语音 token，但实际显示语言为 `ArchiveLanguage.UNKNOWN`。
- 未知 Steam 语言映射为空 token、`ArchiveLanguage.UNKNOWN`、空 token。
- `summarize_fh6_languages()` 是纯函数，测试前后的语言 ZIP 路径和内容不发生变化。
- 非英语 Steam token 保留为规范化 token，但实际显示语言为未知。
- 现有语言包启用、还原、恢复和三游戏启动测试继续通过。

### 8.2 后续前端可见验收（本轮不执行）

在当前 `SWAPPED` 状态下，简体中文 GUI 应稳定显示：

```text
当前 FH6 游戏使用语言：英语
实际显示语言：中文
语音语言：英语
```

连续观察至少十二秒，跨过两次五秒周期扫描，标题、三行语言信息和按钮位置不得闪烁或上下移动。

本轮不把该可见验收写成已通过。

## 9. 文档同步

本轮实现后更新 `docs/PROJECT_STATE.md`，记录问题原因、底层 API、自动测试以及前端仍未接入。检查老三样中的长期边界并记录“Steam 游戏内容语言不是 Steam 客户端界面语言”；不得把延后的前端和抖动修复写成已完成。

## 10. 不在本次范围

- 自动修改 Steam 的 FH6 游戏语言。
- 支持或交换 FH4/FH5 语言文件。
- 从音频文件、运行时内存或网络服务识别语音语言。
- 改变现有语言包改名流程或扩大非英语 Steam 游戏语言下的启用范围。
- 修改 GUI/TUI、翻译 catalog 或五秒刷新布局。
