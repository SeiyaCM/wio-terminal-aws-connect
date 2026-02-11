# wio-terminal-aws-connect

WIO TerminalとAWS IoT Coreを連携させたセンサーデータ収集・可視化システム

## 参考サイト
- [aws-labs-mcp](https://github.com/awslabs/mcp/tree/main/src)

## プロジェクト構成

```
wio-terminal-aws-connect/
├── level-1/                    # Level 1: 基本的なIoTデータパイプライン
│   ├── device/                 # WIO Terminal用デバイスコード
│   │   └── wioterminal.ino    # Arduinoスケッチ
│   └── infra/                  # AWS CDKインフラコード
│       ├── app.py             # CDKアプリケーションエントリーポイント
│       ├── infra/
│       │   └── infra_stack.py # インフラスタック定義
│       └── tests/             # テストコード
└── level-2/                    # Level 2: 高度な分析・機械学習機能（未実装）
```

## Level 1: 基本的なIoTデータパイプライン

### アーキテクチャ

```
WIO Terminal → AWS IoT Core → IoT Rule → DynamoDB
                                            ↓
                                       Glue Crawler
                                            ↓
                                      Glue Data Catalog
                                            ↓
                                          Athena
                                            ↓
                                        QuickSight (オプション)
```

### デプロイされるAWSリソース

- **DynamoDB**: センサーデータの時系列ストレージ
- **IoT Core & IoT Rule**: MQTTメッセージの受信と処理
- **Glue Database & Crawler**: データカタログとメタデータ管理
- **Athena WorkGroup**: DynamoDBデータのクエリ実行環境
- **S3 Buckets**: Athenaクエリ結果とスピルデータの保存
- **IAM Roles**: 各サービス間の権限管理
- **CloudWatch Logs**: エラーログの記録

## セットアップ手順

### 前提条件

1. **AWS CLI**: インストール済みで認証情報が設定されていること
2. **AWS CDK CLI**: `npm install -g aws-cdk`
3. **Python 3.9+**: pyenvまたはシステムPython
4. **uv**: Pythonパッケージマネージャー
   ```bash
   # Windowsの場合
   pip install uv
   # または
   brew install uv  # Homebrewを使用している場合
   ```
5. **aws-vault**: AWS認証情報管理ツール（推奨）
6. **Node.js**: CDK CLIの実行に必要

### 1. リポジトリのクローン

```bash
git clone <repository-url>
cd wio-terminal-aws-connect
```

### 2. Level 1インフラのデプロイ

#### 2.1 依存関係のインストール

```bash
cd level-1/infra
uv sync
```

#### 2.2 仮想環境の有効化

```bash
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Windows (CMD)
.venv\Scripts\activate.bat

# macOS/Linux
source .venv/bin/activate
```

#### 2.3 CDK Bootstrapの実行（初回のみ）

```bash
# aws-vaultを使用する場合
aws-vault exec <profile-name> --no-session -- cdk bootstrap

# 直接AWS CLIを使用する場合
cdk bootstrap
```

#### 2.4 スタックの合成（確認）

```bash
# aws-vaultを使用する場合
aws-vault exec <profile-name> --no-session -- cdk synth

# 直接AWS CLIを使用する場合
cdk synth
```

#### 2.5 デプロイの実行

```bash
# aws-vaultを使用する場合
aws-vault exec <profile-name> --no-session -- cdk deploy --require-approval never

# 直接AWS CLIを使用する場合
cdk deploy --require-approval never
```

デプロイには約2-3分かかります。完了すると以下のメッセージが表示されます:

```
✅  attempt-iot-monitoring-stack

Stack ARN:
arn:aws:cloudformation:ap-northeast-1:XXXXXXXXXXXX:stack/attempt-iot-monitoring-stack/...
```

### 3. デプロイの確認

#### 3.1 CloudFormationスタックの確認

```bash
aws cloudformation describe-stacks --stack-name attempt-iot-monitoring-stack
```

#### 3.2 DynamoDBテーブルの確認

```bash
aws dynamodb describe-table --table-name attempt-dynamodb-sensor-data
```

#### 3.3 IoT Ruleの確認

```bash
aws iot get-topic-rule --rule-name attempt_iot_rule_sensor_data
```

#### 3.4 Glue Crawlerの確認

```bash
aws glue get-crawler --name attempt-glue-crawler-sensor-data
```

### 4. WIO Terminalの設定

#### 4.1 AWS IoT Coreでデバイスを登録

1. AWS IoT Coreコンソールにアクセス
2. 「管理」→「モノ」→「モノを作成」
3. デバイス証明書とキーをダウンロード
4. ポリシーをアタッチ（IoT Coreへのパブリッシュ権限）

#### 4.2 Arduino IDEの設定

1. Arduino IDEをインストール
2. WIO Terminal用のボードマネージャーを追加
3. 必要なライブラリをインストール:
   - WiFi
   - MQTT
   - ArduinoJson

#### 4.3 デバイスコードの書き込み

```bash
cd level-1/device
# wioterminal.inoをArduino IDEで開く
# WiFi認証情報とAWS IoT Core接続情報を設定
# WIO Terminalに書き込み
```

### 5. データフローのテスト

#### 5.1 テストメッセージの送信

```bash
aws iot-data publish \
  --topic "device/test-device-001/data" \
  --payload '{"device_id":"test-device-001","timestamp":1640995200,"temperature":25.5,"humidity":60.2}'
```

#### 5.2 DynamoDBでデータを確認

```bash
aws dynamodb scan \
  --table-name attempt-dynamodb-sensor-data \
  --limit 10
```

#### 5.3 Glue Crawlerの実行

```bash
# Crawlerを手動実行
aws glue start-crawler --name attempt-glue-crawler-sensor-data

# ステータス確認
aws glue get-crawler --name attempt-glue-crawler-sensor-data
```

#### 5.4 Athenaでクエリ実行

```bash
# クエリを実行
aws athena start-query-execution \
  --query-string "SELECT * FROM \"attempt-glue-database-sensor\".\"attempt_dynamodb_sensor_data\" LIMIT 10" \
  --result-configuration "OutputLocation=s3://attempt-s3-athena-results-<ACCOUNT_ID>-<REGION>/" \
  --work-group attempt-athena-workgroup-sensor

# 結果を確認（QUERY_EXECUTION_IDは上記コマンドの出力から取得）
aws athena get-query-results --query-execution-id <QUERY_EXECUTION_ID>
```

### 6. オプション機能の有効化

現在のCDKデプロイでは、QuickSightとAthena DynamoDB Connectorがコメントアウトされています。これらは必要に応じて追加できます。

#### 6.1 現在の構成で利用可能な機能

CDKでデプロイ済みの構成で、以下が既に利用可能です:

✅ **IoT CoreからDynamoDBへのデータ保存**
✅ **Glue CrawlerによるDynamoDBテーブルのカタログ化**
✅ **AthenaでのDynamoDBデータクエリ**（Glue Catalog経由）
✅ **S3へのクエリ結果保存**

基本的なデータ分析は、Glue CrawlerとAthenaの組み合わせで十分に実現できます:

```sql
-- Glue Crawlerでカタログ化されたテーブルをクエリ
SELECT * FROM "attempt-glue-database-sensor"."attempt_dynamodb_sensor_data"
WHERE device_id = 'test-device-001'
ORDER BY timestamp DESC
LIMIT 10;
```

#### 6.2 QuickSight（データ可視化）の設定

**推奨方法: AWSコンソールで手動作成**

QuickSightは初回セットアップが必要で、CDKでの自動化が難しいため、コンソールでの作成が適しています。

##### 手順:

1. **QuickSightのサインアップ**
   - AWSコンソール → QuickSight
   - 初回は「Sign up for QuickSight」をクリック
   - Enterprise版またはStandard版を選択（Standard版で十分）
   - リージョンを選択（ap-northeast-1推奨）

2. **権限設定**
   - 「Manage QuickSight」→「Security & permissions」
   - 「Add or remove」をクリック
   - ✅ Amazon Athena
   - ✅ Amazon S3
     - 「Select S3 buckets」で以下を選択:
       - `attempt-s3-athena-results-*`
       - `attempt-s3-athena-spill-*`

3. **データソースの作成**
   - QuickSightホーム → 「Datasets」→「New dataset」
   - 「Athena」を選択
   - Data source name: `AttemptSensorData`
   - WorkGroup: `attempt-athena-workgroup-sensor`を選択
   - 「Create data source」をクリック

4. **データセットの作成**
   - Database: `attempt-glue-database-sensor`を選択
   - Table: `attempt_dynamodb_sensor_data`を選択
   - 「Select」をクリック

5. **ダッシュボードの作成**
   - 「New analysis」をクリック
   - ビジュアライゼーションを追加:
     - 時系列グラフ（温度・湿度の推移）
     - ゲージ（現在値）
     - テーブル（最新データ一覧）
   - フィルターを設定（デバイスID、日時範囲など）

**CDKで作成する必要性**: 低い（手動の方が柔軟で簡単）

##### CDKで作成する場合（非推奨）:

QuickSightのセットアップ完了後、`level-1/infra/infra/infra_stack.py`のQuickSightリソースのコメントを解除して再デプロイできますが、以下の制約があります:

- QuickSightユーザーが事前に存在する必要がある
- ユーザーARNを正確に指定する必要がある
- エラーが発生しやすい

#### 6.3 Athena DynamoDB Connector（高度なクエリ）

**推奨方法: 基本的には不要（Glue Crawlerで十分）**

現在の構成では、Glue CrawlerがDynamoDBテーブルをカタログ化しているため、基本的なクエリは既に可能です。

##### Athena DynamoDB Connectorが必要なケース:

| ケース | 説明 | 必要性 |
|--------|------|--------|
| **リアルタイムクエリ** | Glue Crawlerは定期実行（デフォルト: 毎日2時）なので、最新データが反映されるまでタイムラグがある | 中 |
| **複雑なクエリ** | DynamoDB特有のデータ型（Map、List、Set）を直接クエリしたい | 低 |
| **パフォーマンス** | 大量データの高速スキャンが必要 | 低 |

##### AWSコンソールでAthena DynamoDB Connectorを作成する方法:

必要な場合は、以下の手順で作成できます:

1. **AWS Serverless Application Repositoryから直接デプロイ**
   - AWSコンソール → Serverless Application Repository
   - 「Public applications」を選択
   - 検索ボックスに「AthenaDynamoDBConnector」と入力
   - 「AthenaDynamoDBConnector」をクリック
   - 「Deploy」をクリック

2. **パラメータを設定**
   - Application name: `AthenaDynamoDBConnector`（デフォルト）
   - AthenaCatalogName: `attempt-athena-catalog-dynamodb`
   - SpillBucket: `attempt-s3-athena-spill-<ACCOUNT_ID>-ap-northeast-1`
     - （既にCDKでデプロイ済みのバケット名を指定）
   - LambdaMemory: `3008`
   - LambdaTimeout: `900`
   - DisableSpillEncryption: `false`
   - 「I acknowledge that this app creates custom IAM roles」にチェック
   - 「Deploy」をクリック

3. **デプロイ完了を確認**
   - CloudFormationスタックが`CREATE_COMPLETE`になるまで待機（約2-3分）
   - Lambda関数が作成されたことを確認

4. **Athena Data Catalogを作成**
   - AWSコンソール → Athena → Data sources
   - 「Create data source」をクリック
   - 「Query a data source」→「Amazon DynamoDB」を選択
   - 「Next」をクリック
   - Data source name: `attempt-athena-catalog-dynamodb`
   - Lambda function: デプロイされたConnector関数を選択
     - 関数名: `attempt-athena-catalog-dynamodb`
   - 「Create data source」をクリック

5. **クエリ実行**
   ```sql
   -- DynamoDB Connector経由でクエリ
   SELECT * FROM "attempt-athena-catalog-dynamodb"."default"."attempt-dynamodb-sensor-data"
   WHERE device_id = 'test-device-001'
   LIMIT 10;
   ```

##### CDKで作成する場合（上級者向け）:

`level-1/infra/infra/infra_stack.py`のAthena DynamoDB Connectorのコメントを解除できますが、以下の問題があります:

- Lambda関数のARNを正しく参照する必要がある
- Serverless Application Repositoryのデプロイが複雑
- エラーが発生しやすい

現時点では、AWSコンソールからのデプロイを推奨します。

#### 6.4 オプション機能の比較表

| 機能 | 推奨方法 | 必要性 | 理由 |
|------|---------|--------|------|
| **QuickSight** | AWSコンソール | 高（可視化が必要な場合） | 初回セットアップが必要、手動の方が柔軟 |
| **Athena DynamoDB Connector** | 不要（Glue Crawlerで十分） | 低 | 基本的なクエリは既に可能 |
| **Athena DynamoDB Connector（必要な場合）** | AWSコンソール（SAR経由） | 中（リアルタイムクエリが必要な場合） | CDKでの実装が複雑、コンソールの方が確実 |

### 7. モニタリングとトラブルシューティング

#### 7.1 IoT Ruleのエラーログ確認

```bash
aws logs tail /aws/iot/rule/attempt-iot-rule-sensor-data/errors --follow
```

#### 7.2 CloudWatch Logsの確認

```bash
# ロググループ一覧
aws logs describe-log-groups

# 特定のロググループのストリーム確認
aws logs describe-log-streams --log-group-name /aws/iot/rule/attempt-iot-rule-sensor-data/errors
```

#### 7.3 DynamoDBのメトリクス確認

AWS CloudWatchコンソールで以下を確認:
- 読み取り/書き込みキャパシティユニット
- スロットリングイベント
- レイテンシー

### 8. クリーンアップ

すべてのリソースを削除する場合:

```bash
cd level-1/infra

# aws-vaultを使用する場合
aws-vault exec <profile-name> --no-session -- cdk destroy

# 直接AWS CLIを使用する場合
cdk destroy
```

このコマンドは以下を削除します:
- DynamoDBテーブルとデータ
- IoT Rules
- Glue CrawlerとDatabase
- S3バケットとコンテンツ
- Athena WorkGroup
- IAMロールとポリシー

## トラブルシューティング

### CDKデプロイエラー

#### エラー: "Unable to resolve AWS account to use"

**原因**: AWS認証情報が設定されていない、またはCDKがアカウント情報を取得できない

**解決策**:
```bash
# AWS認証情報を確認
aws sts get-caller-identity

# aws-vaultを使用
aws-vault exec <profile-name> --no-session -- cdk deploy
```

#### エラー: "ModuleNotFoundError: No module named 'aws_cdk'"

**原因**: 仮想環境が有効化されていない、または依存関係がインストールされていない

**解決策**:
```bash
# 仮想環境を有効化
.venv\Scripts\Activate.ps1  # Windows PowerShell

# 依存関係を再インストール
uv sync
```

#### エラー: QuickSight DataSource作成失敗

**原因**: QuickSightがアカウントで有効化されていない

**解決策**: QuickSightリソースをコメントアウト（デフォルトで対応済み）

### WIO Terminal接続エラー

#### WiFi接続失敗

- SSIDとパスワードを確認
- 2.4GHz WiFiを使用していることを確認
- ファイアウォール設定を確認

#### MQTT接続失敗

- AWS IoT Coreのエンドポイントを確認
- デバイス証明書とキーが正しいことを確認
- IoTポリシーでパブリッシュ権限が付与されていることを確認

## 開発ガイド

### テストの実行

```bash
cd level-1/infra

# ユニットテスト
pytest tests/unit/ -v

# 統合テスト
pytest tests/integration/ -v

# すべてのテスト
pytest tests/ -v
```

### コードフォーマット

```bash
# Black（コードフォーマッター）
black infra/

# Flake8（リンター）
flake8 infra/

# MyPy（型チェック）
mypy infra/
```

## セキュリティベストプラクティス

1. **IAMロール**: 最小権限の原則に従う
2. **S3バケット**: パブリックアクセスをブロック、暗号化を有効化
3. **DynamoDB**: ポイントインタイムリカバリを有効化
4. **IoT証明書**: 定期的にローテーション
5. **CloudWatch Logs**: エラーログを監視

## コスト最適化

- **DynamoDB**: オンデマンド課金モードを使用（低トラフィック時）
- **S3**: ライフサイクルポリシーで古いデータをアーカイブ
- **Athena**: クエリ結果をキャッシュして再利用
- **Glue Crawler**: スケジュール実行を最適化（デフォルト: 毎日2時）

## ライセンス

MIT License

## サポート

問題が発生した場合:
1. CloudWatch Logsでエラーを確認
2. IAM権限が正しく設定されているか確認
3. AWSサービスクォータを確認
4. CDK合成出力でリソース設定を確認
