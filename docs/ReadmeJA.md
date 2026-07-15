<p align="right">
  <a href="../README.md">简体中文</a> •
  <a href="ReadmeEN.md">English</a> •
  <strong>日本語</strong>
</p>

<div align="center">
  <img src="../src/data/icon.png" alt="FH-DualSense-Enhanced" width="180">
  <h1>FH-DualSense-Enhanced</h1>
  <p><strong>PC 版 Forza Horizon に DualSense のアダプティブトリガーとテレメトリ駆動の握把触覚を追加します。</strong></p>
</div>

FH-DualSense-Enhanced `R4` は、`Forza-Horizon-DualSense-Python 1.6.2` を基にし、`HorizonHaptics 1.3.0` を参考にした拡張版です。ゲームが UDP で送信する車両テレメトリを読み取り、ブレーキ、アクセル、エンジン、路面、タイヤ、衝突の状態を DualSense のフィードバックに変換します。

このプロジェクトは上流プロジェクトの公式リリースではなく、上流作者の見解を示すものでもありません。

R2 からは、簡潔で上流の公式版と誤認されにくい独自の `R` バージョン体系を採用します。過去の Enhanced R1 は `1.6.2.post1` を使用していましたが、現在の製品バージョンには上流の基礎バージョンを含めません。

## 主な機能

- L2 トリガーはブレーキ量に応じた抵抗と GT7 風 ABS wall を提供し、上部の抵抗壁を保ちながら下部ゾーンをパルスさせます。
- R2 トリガーの動的 wheelspin は、駆動輪スリップ、低速の車輪回転、非対称 EWMA、ヒステリシス、G 力減衰から生成され、レブリミッターより優先されます。
- グリップフィードバックはペダル状態に応じて振り分けられます。ブレーキだけなら L2、アクセルだけなら R2 トリガー、両方なら R2 トリガーへ出力され、L2 の ABS は独立して動作します。
- 舗装、水たまり、土、砂利では、R2 トリガーに異なる材質周波数帯を使用します。
- エンジン、路面材質、サスペンション、衝突、水たまり、タイヤスリップ、バーンアウト、ABS に対応した握把触覚を備えています。
- R2 トリガーのレッドラインと握把レッドラインは別々のスイッチを使用します。既定では R2 トリガー側を無効、握把側を有効にし、左握把へ識別しやすい非線形の燃料カットパルスと開始衝撃を出力します。
- 衝突触覚は方向付きの包絡を使用します。任意の握把シフトショックは既定で無効で、強度と持続時間を独立して調整できます。
- ターボブースト抵抗、G 力アクセル抵抗、L2/R2 衝突ショック、トリガーを離した時の路面テクスチャは個別に有効化でき、既定では無効です。
- タコメーターライトバー、レッドライン点滅、ギア Player LEDs も既定では無効で、USB と Bluetooth で同じ状態を使用します。
- 車両が完全に停止してアイドリングしているときは、意味のない連続振動を発生させません。
- 停車中の空ぶかしやバーンアウトでは、車両状態に合ったフィードバックが発生します。
- 路面材質の効果は、車両の移動またはタイヤの空転による実際の励振がある場合だけ加わります。
- USB と Bluetooth の両方に対応します。
- Miku Console、Miku Stage、Miku Studio は同一のバックエンド、ページ、設定、プロファイル形式を共有し、レイアウトだけが異なります。
- Windows 単体 EXE はアプリ内更新確認、ダウンロード、SHA-256 検証、再起動インストール、失敗時ロールバックに対応します。ZUV は任意の互換・開発経路として残ります。
- グリップ、ABS、レッドライン、衝突の詳細設定は折りたたまれた「実験的機能」にまとめられ、握把シフトショックは通常設定にあります。

既定の調整値はコミュニティのフィードバックを参考にし、実際の走行テストで調整されています。多くの環境で使いやすい出発点ですが、すべての車両やプレイヤーに最適とは限りません。

## USB と Bluetooth

USB と Bluetooth は同じ左右ステレオ波形合成を使用します。どちらでもアダプティブトリガー、路面、エンジン、レッドライン、方向付き衝突の触覚を利用できます。

| 接続方式 | 出力方式 |
| --- | --- |
| USB | DualSense の 4 チャンネル音声エンドポイントで左右の触覚を出力し、HID でトリガーを制御します |
| Bluetooth | HID report `0x36` で 3 kHz の左右ステレオ HD haptics を直接送信し、トリガー状態は引き続き HID で制御します |

PC、コントローラーのファームウェア、Bluetooth アダプターによって細かな差が生じる場合があります。Bluetooth HD haptics を開始できない場合は compatible rumble へ自動的に切り替わり、触覚の失敗がトリガーを停止させることはありません。

## クイックインストール

### Windows の推奨方法：単体 EXE

1. [最新 Release](https://github.com/piereacy/FH-DualSense-Enhanced/releases/latest) を開きます。
2. 好みのレイアウトを一つ選びます。三つの機能とプロファイル互換性は同じです。
   - `FH-DualSense-Enhanced-R4-Miku-Console.exe`：完全な文字サイドバーを持つ、狭い画面でも安定した構成。
   - `FH-DualSense-Enhanced-R4-Miku-Stage.exe`：上部ナビゲーションと広い作業領域。
   - `FH-DualSense-Enhanced-R4-Miku-Studio.exe`：コンパクトなナビゲーションと調整向けワークスペース。
3. EXE を直接実行します。Python、BAT、ZUV、uv は不要で、設定は隣の `data` フォルダーに保存されます。
4. 「システムと更新」から確認、ダウンロード、検証、再起動インストールを実行できます。自動確認は既定で有効、バックグラウンドダウンロードは無効です。

置換に失敗した場合、独立した Helper が旧 EXE を復元します。管理者権限を黙って要求することはなく、ソース、Linux、ZUV 実行時には Windows EXE の置換操作を表示しません。

### 任意の ZUV 経路

従来どおり `win_start.bat` だけをダウンロードすることもできます。ランチャーが `FH-DualSense-Enhanced.zuv.py` を取得し、uv と分離された Python 環境を準備します。

ネットワークが不安定な場合は `FH-DualSense-Enhanced.zuv.py` を手動でダウンロードして `win_start.bat` の隣へ置くと、ローカルファイルが優先されます。R4 単体 EXE に ZUV は不要です。

ローリングテスト版を試す場合は `R4-preview` Release を使用し、`uv run FH-DualSense-Enhanced.zuv.py --prerelease` でプレリリースチャンネルを追跡できます。

### Linux

`linux_start.sh` をダウンロードして実行します。ランチャーはアプリのダウンロードと起動だけを行い、システムの udev ルールはインストールしません。ログに DualSense の権限不足が表示された場合は、[`70-dualsense.rules`](../packaging/linux/70-dualsense.rules) をダウンロードして、次を実行してください。

```bash
sudo cp 70-dualsense.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

完了後、USB コントローラーを接続し直すか、Bluetooth コントローラーを再ペアリングしてください。

## 必須のゲーム設定

### 1. Steam Input を有効にする

Steam ライブラリでゲームを右クリックし、**プロパティ -> コントローラー** を開いて、そのゲームの Steam Input を有効にします。Steam の DualSense 振動サポートも有効にしてください。

Steam Input はボタン割り当てとゲーム本来の振動を担当します。本アプリはアダプティブトリガーとテレメトリ駆動の握把触覚を追加します。

### 2. Forza Data Out を有効にする

Forza Horizon の **設定 -> HUD とゲームプレイ** を開き、Data Out の項目までスクロールします。

| 設定 | 値 |
| --- | --- |
| Data Out | ON |
| Data Out IP Address | `127.0.0.1` |
| Data Out IP Port | `5300` |

`127.0.0.1` でパケットを受信できない場合は、IPv6 ループバックアドレス `::1` を試し、アプリ側でも同じ待受アドレスを使用してください。

### 3. 起動順序

1. DualSense コントローラーを接続します。
2. FH-DualSense-Enhanced を起動します。
3. コントローラーが認識され、UDP の待受が開始されたことを確認します。
4. ゲームを起動します。

SISR などコントローラーを占有する可能性があるツールを使用する場合は、最初に FH-DualSense-Enhanced を起動し、その後でツールとゲームを起動してください。

### 4. ゲーム内の振動設定

握把触覚はテレメトリから独立して合成されるため、ゲーム内の振動設定には依存しません。有効のままならメニュー、カットシーンなどのゲーム本来の振動を維持できますが、その振動が本プロジェクトの左右衝突方向を隠す場合があります。方向確認や重複比較ではゲーム内振動を無効にしてください。本プロジェクトは現在、ゲーム本来の振動を取得または完全再現しません。

## DualSense ボタンアイコン

Forza Horizon 6 の画面に PlayStation / DualSense のボタン表示を使用したい場合は、Nexus Mods の [PlayStation Controller Icons (DualSense)](https://www.nexusmods.com/forzahorizon6/mods/2) を利用できます。標準の Xbox ボタン表示を DualSense アイコンへ置き換える Mod です。

ゲームのアップデートによって、置き換えた画面ファイルが元に戻る場合があります。ゲーム更新後は、その都度 Mod ファイルをもう一度コピーして置き換えてください。

## 握把触覚の仕組み

アプリは固定波形を再生したり、状況を無視して振動し続けたりしません。すべてのレイヤーはリアルタイムのテレメトリから生成されます。

- エンジンレイヤーは RPM、負荷、アクセルに追従します。
- 路面レイヤーは速度、車輪回転、路面材質に追従します。
- スリップレイヤーは通常走行、グリップ喪失、停車中のバーンアウトを区別します。
- ABS はブレーキとタイヤの条件を満たしたときだけ作動します。
- 衝突、サスペンション、水たまりの各レイヤーは対応するイベントが発生したときだけ作動します。

**設定 -> 握把触覚** から、全体、エンジン、路面、衝突、スリップの強度を調整できます。握把触覚だけを無効にして、アダプティブトリガーを有効のまま残すこともできます。

## バックグラウンド動作

次の 2 項目は個別に設定できます。

- ゲーム終了時にアプリも終了する。
- ウィンドウを最小化したときにシステムトレイへ移動する。

どちらも必須ではありません。

## ファイアウォールとネットワーク

アプリはローカル UDP ポートを待ち受けるだけで、テレメトリをインターネットへアップロードしません。

ログに `No UDP packets yet` が表示され続ける場合:

1. Data Out、IP アドレス、ポートが正しいことを確認します。
2. Windows ファイアウォールで EXE を許可します。BAT モードでは、使用される `python.exe` と UDP 5300 も許可します。
3. 別のアプリインスタンスがすでに起動していないか確認します。
4. ファイアウォールを無効にするのは一時的な診断比較だけにし、確認後はすぐに有効へ戻してください。無効のまま使用しないでください。

## トラブルシューティング

| 症状 | 対処方法 |
| --- | --- |
| `No UDP packets yet` | Data Out、待受アドレス、UDP 5300、ファイアウォール規則を確認し、必要なら `::1` を試します |
| `WinError 10048` | UDP 5300 がすでに使用されています。重複したアプリインスタンスまたは別の待受プログラムを終了します |
| DualSense が見つからない | 接続、Steam による占有、HidHide の許可リストを確認します。BAT モードでは通常 `python.exe` の許可が必要です |
| USB 握把触覚を開始できない | Windows に DualSense の 4 チャンネル音声エンドポイントが表示されていることを確認し、それを使用中のアプリを閉じて USB を接続し直します |
| `PaErrorCode -9999` または WDM-KS エラー | アプリの互換バックエンドへの自動切り替えを待ちます。失敗が続く場合は Windows Audio とコントローラー音声デバイスを確認してください。トリガー機能は引き続き利用できます |
| Bluetooth HD haptics のフォールバックがログに出る | 現在の接続が report `0x36` を拒否しました。compatible rumble は継続し、コントローラーの再接続後に HD haptics を再試行します |
| トリガーまたは握把触覚が強すぎる | 設定で該当する強度を下げるか、車両専用のプロファイルを作成します |

## 開発とビルド

```powershell
git clone https://github.com/piereacy/FH-DualSense-Enhanced.git
cd FH-DualSense-Enhanced\src
uv sync
uv run main.py
```

テストを実行:

```powershell
uv run --project src pytest -q
```

ZUV をビルド:

```powershell
set UPDATE_REPO=piereacy/FH-DualSense-Enhanced
packaging\zuv\build_zuv.bat
```

Windows EXE をビルド:

```powershell
packaging\windows\build_exe.bat
```

## プロジェクトの由来とライセンス

FH-DualSense-Enhanced は次のプロジェクトを変更したものです。

Originally created by Hamza Yeşilmen (HamzaYslmn).

Source: <https://github.com/HamzaYslmn/Forza-Horizon-DualSense-Python>

握把触覚と USB チャンネルの実装では [HorizonHaptics](https://github.com/haritha99ch/HorizonHaptics) を、Bluetooth HD haptics プロトコルでは [vDS](https://github.com/hurryman2212/vds) を参照しています。MIT ライセンス表記は [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) に収録されています。

本プロジェクトは、個人かつ非商用利用に限定した独自のソース公開ライセンスを採用しています。コピー、変更、再配布を行う前に [LICENSE](../LICENSE) を全文確認してください。
