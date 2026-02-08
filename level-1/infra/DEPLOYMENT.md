# CDK Deployment and Verification Guide

This guide provides instructions for deploying and verifying the WIO Terminal IoT infrastructure.

## Prerequisites

1. AWS CLI configured with appropriate credentials
2. AWS CDK CLI installed (`npm install -g aws-cdk`)
3. Python 3.9+ with uv package manager
4. AWS account with necessary permissions

## Deployment Steps

### 1. Install Dependencies

```bash
cd level-1/infra
uv sync
```

### 2. Bootstrap CDK (First Time Only)

If this is your first time using CDK in your AWS account/region:

```bash
cdk bootstrap
```

### 3. Synthesize CloudFormation Template

Verify the CDK stack can be synthesized without errors:

```bash
cdk synth
```

This will generate a CloudFormation template and display it in the console.

### 4. Review Changes

Before deploying, review what resources will be created:

```bash
cdk diff
```

### 5. Deploy the Stack

Deploy the infrastructure to AWS:

```bash
cdk deploy
```

You will be prompted to approve security-related changes (IAM roles, policies). Review and approve them.

### 6. Verify Deployment

After deployment completes, verify the resources were created:

```bash
# List CloudFormation stacks
aws cloudformation describe-stacks --stack-name wio-terminal-infra-stack

# Verify DynamoDB table
aws dynamodb describe-table --table-name wio-terminal-sensor-data

# Verify IoT Rule
aws iot get-topic-rule --rule-name WioTerminalSensorDataRule

# Verify Glue Crawler
aws glue get-crawler --name wio-terminal-sensor-data-crawler

# Verify Athena WorkGroup
aws athena get-work-group --work-group wio-terminal-sensor-workgroup
```

## End-to-End Data Flow Verification

### 1. Test IoT Data Ingestion

Publish a test message to the IoT topic:

```bash
aws iot-data publish \
  --topic "device/test-device-001/data" \
  --payload '{"device_id":"test-device-001","timestamp":1640995200,"sensors":{"temperature":25.5,"humidity":60.2}}'
```

### 2. Verify Data in DynamoDB

Check that the data was written to DynamoDB:

```bash
aws dynamodb scan \
  --table-name wio-terminal-sensor-data \
  --limit 10
```

### 3. Run Glue Crawler

Manually trigger the Glue Crawler to catalog the DynamoDB table:

```bash
aws glue start-crawler --name wio-terminal-sensor-data-crawler
```

Check crawler status:

```bash
aws glue get-crawler --name wio-terminal-sensor-data-crawler
```

### 4. Query Data with Athena

After the crawler completes, query the data using Athena:

```bash
# Start query execution
aws athena start-query-execution \
  --query-string "SELECT * FROM \"wio-terminal-sensor-database\".\"wio_terminal_sensor_data\" LIMIT 10" \
  --result-configuration "OutputLocation=s3://wio-terminal-athena-results-{ACCOUNT_ID}-{REGION}/" \
  --work-group wio-terminal-sensor-workgroup
```

Replace `{ACCOUNT_ID}` and `{REGION}` with your AWS account ID and region.

### 5. Configure QuickSight (Manual Steps)

QuickSight requires some manual configuration:

1. Sign up for QuickSight if not already done
2. Grant QuickSight access to Athena and S3 buckets
3. Create a dataset using the Athena data source
4. Build visualizations and dashboards

## Testing

### Run Unit Tests

```bash
pytest tests/unit/ -v
```

### Run Integration Tests

```bash
pytest tests/integration/ -v
```

### Run All Tests

```bash
pytest tests/ -v
```

## Monitoring and Troubleshooting

### Check IoT Rule Errors

View CloudWatch Logs for IoT Rule errors:

```bash
aws logs tail /aws/iot/rule/WioTerminalSensorDataRule/errors --follow
```

### Check Lambda Function Logs (Athena Connector)

```bash
aws logs tail /aws/lambda/wio-terminal-dynamodb-catalog --follow
```

### Verify IAM Permissions

Ensure the IoT Rule role has permissions to write to DynamoDB:

```bash
aws iam get-role --role-name {IoTRuleRoleName}
aws iam list-attached-role-policies --role-name {IoTRuleRoleName}
```

## Cleanup

To remove all resources and avoid ongoing charges:

```bash
cdk destroy
```

This will delete all resources created by the stack, including:
- DynamoDB table and data
- IoT Rules
- Glue Crawler and Database
- S3 buckets and contents
- Athena WorkGroup and Data Catalog
- QuickSight Data Source
- IAM roles and policies

## Architecture Verification

The deployed infrastructure implements the following data flow:

```
WIO Terminal → IoT Core → IoT Rule → DynamoDB
                                        ↓
                                   Glue Crawler
                                        ↓
                                  Glue Data Catalog
                                        ↓
                                      Athena
                                        ↓
                                    QuickSight
```

### Key Components

1. **IoT Core**: Receives MQTT messages on topic `device/+/data`
2. **IoT Rule**: Processes messages with SQL and writes to DynamoDB
3. **DynamoDB**: Stores time-series sensor data with `device_id` and `timestamp` keys
4. **Glue Crawler**: Catalogs DynamoDB table metadata daily
5. **Athena**: Queries DynamoDB data using the DynamoDB Connector
6. **QuickSight**: Visualizes data from Athena

### Security Features

- S3 buckets encrypted with AES256
- Public access blocked on all S3 buckets
- IAM roles follow least privilege principle
- DynamoDB point-in-time recovery enabled
- CloudWatch Logs for error tracking

## Requirements Validation

This deployment satisfies the following requirements:

- **Requirement 1.1**: IoT Core receives and processes device data
- **Requirement 1.2**: Error logging via CloudWatch Logs
- **Requirement 2.1**: Data processing rules applied via IoT Rule SQL
- **Requirement 2.3**: Processed data stored in DynamoDB
- **Requirement 3.1**: Data persisted in DynamoDB
- **Requirement 3.4**: Data integrity and consistency guaranteed
- **Requirement 4.1**: Athena enables data querying
- **Requirement 4.2**: Glue Crawler catalogs metadata
- **Requirement 4.3-4.5**: QuickSight provides visualization
- **Requirement 5.1-5.5**: Infrastructure defined with CDK in Python

## Support

For issues or questions:
1. Check CloudWatch Logs for error messages
2. Verify IAM permissions are correctly configured
3. Ensure AWS service quotas are not exceeded
4. Review the CDK synthesis output for configuration errors
