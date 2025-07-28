# 音声住所抽出アプリ

Google Cloud Speech-to-Textを使用したリアルタイム音声による住所抽出Streamlitアプリケーションです。2つのモードで効率的な住所入力が可能です。

## 機能

### 📋 段階入力モード
- 🔢 **2段階リアルタイム処理**: 郵便番号→詳細住所（建物・部屋番号含む）のリアルタイム音声入力
- 🎤 **連続音声認識**: Google Cloud Speech-to-Textによるストリーミング認識
- ⚡ **自動停止機能**: 郵便番号・基本住所取得時の自動録音停止
- 📍 **郵便番号API連携**: zipcloud APIで郵便番号から基本住所を自動取得
- ⏱️ **処理時間測定**: 郵便番号検索時間の測定・表示
- 🧹 **シンプルクリーンアップ**: 詳細住所のテキスト整理・正規化
- 🔄 **手動進行制御**: 確認後の手動次ステップ移行

### ⚡ 高速モード
- 🎯 **リアルタイム一括入力**: 完全な住所をリアルタイム音声で一度に入力
- 🤖 **Toriyama住所パーサー**: japanese-address-parser-py v0.2.6による高精度住所解析
- 🧹 **シンプルテキスト処理**: 基本的なテキストクリーンアップ（複雑な解析は簡素化）
- ⏱️ **パフォーマンス表示**: 処理時間とクリーンアップ時間の測定
- 🔄 **タブ切り替え**: 段階入力・高速モード間の簡単切り替え

## セットアップ

### 1. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 2. Google Cloud Speech-to-Text の設定

#### Google Cloud プロジェクトの準備
1. [Google Cloud Console](https://console.cloud.google.com/)でプロジェクトを作成または選択
2. Speech-to-Text APIを有効化
3. サービスアカウントキーを作成してJSONファイルをダウンロード

#### 環境変数の設定
`.env`ファイルを作成（`.env.example`を参考に）:

```bash
cp .env.example .env
```

`.env`ファイルを編集:
```env
# Google Cloud プロジェクトID
GOOGLE_CLOUD_PROJECT_ID=your_google_cloud_project_id_here

# 以下のいずれかの方法で認証を設定:
# 方法1: サービスアカウントJSONファイルのパス
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/service-account-key.json

# 方法2: gcloud CLIでの認証（推奨）
# gcloud auth application-default login

# 音声設定（オプション）
AUDIO_SAMPLE_RATE=16000
AUDIO_CHANNELS=1
```

### 3. アプリケーションの起動

```bash
streamlit run app.py
```

## 使用方法

### 📋 段階入力モード

#### ステップ1: 郵便番号・基本住所取得
1. **「郵便番号録音開始」ボタンをクリック**
2. **7桁の郵便番号を話す** (例：「123-4567」または「1234567」)
3. **リアルタイム音声認識が自動実行**
4. **郵便番号が認識されると自動でzipcloud APIから基本住所を取得**
5. **住所取得完了時に録音が自動停止**
6. **処理時間が表示される**（住所取得時間: XXXms）
7. **確認後「次のステップに進む」ボタンをクリック**

#### ステップ2: 詳細住所・建物情報入力
1. **表示された基本住所を確認**
2. **「詳細住所録音開始」ボタンをクリック**
3. **番地・建物名・部屋番号を連続して話す** (例：「1丁目2番3号 ABCマンション405号室」)
4. **リアルタイム音声認識とシンプルテキストクリーンアップが自動実行**
5. **クリーンアップ結果と完成予定住所がリアルタイム表示**
6. **手動で録音停止後「詳細住所入力完了」ボタンをクリック**

#### ステップ3: 完了
1. **統合された完全な住所を確認**
2. **必要に応じて「最初からやり直し」**

### ⚡ 高速モード

1. **「リアルタイム住所録音開始」ボタンをクリック**
2. **完全な住所を一度に話す** (例：「東京都渋谷区神宮前1丁目2番3号 ABCマンション405号室」)
3. **リアルタイム音声認識とToriyama住所パーサーが自動実行**
   - **Google Cloud Speech-to-Textストリーミング認識**: PyAudioによるリアルタイム音声キャプチャ → Google Cloud APIへのストリーミング送信 → 305秒制限対応の自動再接続機能 → 確定テキストと仮認識テキストの分離処理
   - **Toriyama住所パーサーによる住所抽出**: `extract_addresses_from_realtime_text()`メソッドで住所解析実行 → japanese-address-parser-py v0.2.6による高精度解析 → 都道府県・市区町村・町域・建物名・部屋番号の詳細抽出 → 信頼度計算と複数候補の優先度付け → 処理時間測定（パーサー時間・建物抽出時間・信頼度計算時間）
   - **基本的なテキストクリーンアップ**: 句読点除去（、。，．） → 連続空白の正規化 → 不要語句の削除処理 → クリーンアップ時間の測定・表示
4. **処理時間とクリーンアップ時間が表示される**
5. **シンプルクリーンアップ済みテキストが表示される**
6. **手動で録音停止**

## ファイル構成

```
.
├── app.py                      # メインのStreamlitアプリ（タブ切り替え式）
├── realtime_speech_service.py  # Google Cloud Speech-to-Textストリーミング認識
├── postal_code_service.py      # 郵便番号抽出・zipcloud API連携
├── toriyama_address_parser.py  # 日本語住所パーサー（japanese-address-parser-py）
├── address_extractor.py        # 住所抽出ロジック（レガシー）
├── japanese_address_parser.py  # 日本語住所パーサー（レガシー）
├── speech_service.py           # Azure Speech Services（レガシー）
├── requirements.txt            # 依存関係
├── .env.example               # 環境変数テンプレート
├── CLAUDE.md                  # Claude Code用プロジェクト指示書
└── README.md                  # このファイル
```

## 技術仕様

- **言語**: Python 3.8+
- **フレームワーク**: Streamlit 1.28.0+
- **音声処理**: Google Cloud Speech-to-Text API v2.33.0+
- **音声録音**: PyAudio 0.2.11+ (リアルタイムストリーミング)
- **住所パーサー**: japanese-address-parser-py v0.2.6 (Toriyama住所パーサー)
- **郵便番号API**: zipcloud API（無料・制限なし）
- **テキスト処理**: 
  - 段階入力モード: シンプルテキストクリーンアップ（正規表現ベース）
  - 高速モード: シンプルテキストクリーンアップ（複雑な解析は簡素化）
- **リアルタイム処理**: Google Cloud Speechストリーミング認識（305秒制限対応）
- **UI状態管理**: Streamlitセッション状態によるリアルタイム更新制御
- **パフォーマンス**: 処理時間測定・表示機能
- **暖機機能**: Google Cloud Speech APIとPyAudioの事前初期化

## アーキテクチャ詳細

### 主要モジュール

#### RealtimeSpeechService
- **機能**: Google Cloud Speech-to-Textストリーミング認識の実装
- **特徴**: 
  - 305秒制限対応の自動再接続機能
  - PyAudioによるリアルタイム音声ストリーミング
  - 事前暖機機能による初回認識高速化
  - Streamlitセッション状態との統合

#### PostalCodeService
- **機能**: 郵便番号抽出とzipcloud API連携
- **特徴**:
  - 音声認識テキストからの郵便番号抽出（正規表現・数値変換）
  - zipcloud API（無料）による住所検索
  - 7桁郵便番号の正規化処理

#### ToriyamaAddressParser
- **機能**: japanese-address-parser-py v0.2.6のラッパー
- **特徴**:
  - 高精度日本語住所解析
  - 建物名・部屋番号・階数の詳細抽出
  - 処理時間測定とパフォーマンス評価
  - フォールバック機能付きエラーハンドリング

### 処理フロー

#### 段階入力モード
1. **リアルタイム音声認識開始** → RealtimeSpeechService
2. **郵便番号抽出** → PostalCodeService.extract_postal_code()
3. **住所API検索** → PostalCodeService.get_address_by_postal_code()
4. **自動録音停止** → 処理時間測定・表示
5. **詳細住所認識** → シンプルテキストクリーンアップ
6. **住所統合・完了**

#### 高速モード
1. **リアルタイム音声認識開始** → RealtimeSpeechService
2. **住所解析** → ToriyamaAddressParser (簡素化版)
3. **テキストクリーンアップ** → 基本的な正規化処理
4. **結果表示** → 処理時間・クリーンアップ時間表示

## 注意事項

- Google Cloud Speech-to-Text APIの使用には課金が発生する場合があります
- マイクへのアクセス許可が必要です
- インターネット接続が必要です（Google Cloud API・zipcloud APIへのアクセス）
- 住所の認識精度は音声の明瞭さに依存します
- リアルタイム処理のため、ネットワーク状況が認識品質に影響します

## トラブルシューティング

### Google Cloud認証エラーの場合
- `.env`ファイルの`GOOGLE_CLOUD_PROJECT_ID`設定を確認
- `GOOGLE_APPLICATION_CREDENTIALS`パスが正しいか確認
- `gcloud auth application-default login`で認証を実行
- Google Cloud Speech-to-Text APIが有効化されているか確認

### リアルタイム音声認識が動作しない場合
- マイクへのアクセス許可を確認
- PyAudioが正しくインストールされているか確認
- マイクの音量・感度設定を調整
- 静かな環境での録音を推奨

### 郵便番号が正しく認識されない場合
- 7桁の数字を明確に発音（例：「1234567」）
- ハイフン付きで発音（例：「123-4567」または「123の4567」）
- 先頭に不要な0が追加される場合は音声をより明確に発音

### ストリーミング接続エラーの場合
- インターネット接続を確認
- Google Cloud APIの制限に達していないか確認
- 305秒制限による自動再接続を待機

### 処理が重い・遅い場合
- Streamlit初回起動時は暖機処理により初期化に時間がかかります
- ネットワーク状況がリアルタイム処理に影響します
- 複数のタブで同時実行を避ける

### zipcloud API接続エラーの場合
- インターネット接続を確認
- 郵便番号の形式を確認（7桁の数字）
- 存在しない郵便番号でないか確認