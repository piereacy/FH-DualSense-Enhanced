<p align="right">
  <a href="../README.md">English</a> •
  <a href="ReadmeZH.md">简体中文</a> •
  <strong>日本語</strong>
</p>

<div align="center">
  <img src="../src/data/icon.png" alt="FH-DualSense-Enhanced" width="180">
  <h1>FH-DualSense-Enhanced</h1>
  <p><strong>PC 版 Forza Horizon に DualSense のアダプティブトリガーとテレメトリ触覚を追加します。</strong></p>
</div>

FH-DualSense-Enhanced は Forza Horizon の Data Out テレメトリを読み取り、ブレーキ、アクセル、エンジン、路面、タイヤ、衝突のデータを DualSense のフィードバックへ変換します。

`Forza-Horizon-DualSense-Python 1.6.2` を基にし、`HorizonHaptics 1.3.0` を参考にした非公式の拡張版です。

## 主な機能

- L2、R2 トリガーでブレーキ、ABS、アクセル、wheelspin を表現します。
- エンジン、路面、サスペンション、水たまり、タイヤスリップ、衝突の握把触覚を提供します。
- ライブテレメトリから方向付き衝突と路面に応じたグリップフィードバックを生成します。
- USB と Bluetooth で同じトリガーおよびテレメトリ効果を使用します。
- 強度調整、車両別プロファイル、コミュニティを参考にした初期設定に対応します。
- 任意のコントローラーライトとシンプルなデスクトップ UI を備えています。

## ダウンロード

### Windows の推奨方法

1. [最新 Release](https://github.com/piereacy/FH-DualSense-Enhanced/releases/latest) を開きます。
2. `FH-DualSense-Enhanced-R<n>.exe` をダウンロードします。
3. EXE を実行します。Python、BAT、ZUV、uv は不要です。

その他の起動方法：

- Windows ランチャー：`win_start.bat` をダウンロードします。回線が不安定な場合は、先に `FH-DualSense-Enhanced.zuv.py` を同じ場所へ置いてください。
- Linux：`linux_start.sh` をダウンロードします。コントローラーの権限エラーが出る場合は、同梱の [`70-dualsense.rules`](../packaging/linux/70-dualsense.rules) を手動でインストールしてください。

## 必須のゲーム設定

### 1. Steam Input を有効にする

Steam の**ゲームのプロパティ -> コントローラー**を開き、そのゲームの Steam Input を有効にします。Steam の DualSense 振動サポートも有効にしてください。

### 2. Forza Data Out を有効にする

ゲームの**設定 -> HUD とゲームプレイ**を開き、次の値を設定します。

| 設定 | 値 |
| --- | --- |
| Data Out | ON |
| Data Out IP Address | `127.0.0.1` |
| Data Out IP Port | `5300` |

ループバックで受信できない場合は、ゲームとアプリの両方で `::1` を試してください。

### 3. 次の順序で起動する

1. DualSense コントローラーを接続します。
2. FH-DualSense-Enhanced を起動し、コントローラーと UDP 待受が準備できたことを確認します。
3. ゲームを起動します。

> [!IMPORTANT]
> Steam Input は有効のままにし、Forza のゲーム設定にある「振動」は必ず無効にしてください。ゲーム本来の振動が握把触覚と競合して覆い隠すため、ゲーム内振動が有効な状態では握把フィードバックが正常に動作しません。

## USB と Bluetooth

どちらも同じテレメトリ判定を使用し、アダプティブトリガー、路面、エンジン、レッドライン、方向付き衝突に対応します。

| 接続方式 | 説明 |
| --- | --- |
| USB | 握把触覚は DualSense オーディオ、アダプティブトリガーは HID を使用します。 |
| Bluetooth | 触覚とトリガーを HID で送信します。HD haptics が利用できない場合は自動的にフォールバックし、トリガー機能は維持されます。 |

## トラブルシューティング

| 症状 | 確認する内容 |
| --- | --- |
| `No UDP packets yet` | Data Out、待受アドレス、UDP ポート `5300`、Windows ファイアウォールを確認します。 |
| `WinError 10048` | 別のアプリが UDP ポート `5300` を使用しています。重複した待受プログラムを終了します。 |
| DualSense が見つからない | コントローラーを再接続し、Steam、HidHide、またはコントローラーを占有するアプリを確認します。 |
| USB 触覚または `PaErrorCode -9999` | DualSense オーディオを確認し、使用中のアプリを閉じて USB を再接続します。トリガーは引き続き使用できます。 |
| Bluetooth 触覚のフォールバック | コントローラーを再接続して HD haptics を再試行します。フォールバック中もトリガーは使用できます。 |

## DualSense ボタンアイコン

Forza Horizon 6 で PlayStation のボタン表示を使う場合は、[PlayStation Controller Icons (DualSense)](https://www.nexusmods.com/forzahorizon6/mods/2) を利用できます。ゲーム更新後は Mod の再適用が必要になる場合があります。

## クレジットとライセンス

原作者 Hamza Yeşilmen（HamzaYslmn）：
[Forza-Horizon-DualSense-Python](https://github.com/HamzaYslmn/Forza-Horizon-DualSense-Python)

握把触覚は [HorizonHaptics](https://github.com/haritha99ch/HorizonHaptics) を、Bluetooth プロトコルは [vDS](https://github.com/hurryman2212/vds) を参考にしています。関連する表記は [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) に含まれています。

本プロジェクトは、個人かつ非商用利用に限定した独自のソース公開ライセンスを採用しています。コピー、変更、再配布を行う前に [LICENSE](../LICENSE) を確認してください。
