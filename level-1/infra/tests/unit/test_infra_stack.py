import aws_cdk as core
import aws_cdk.assertions as assertions

from infra.infra_stack import InfraStack

def test_iot_core_and_rule_implementation():
    """
    Test IoT Core and IoT Rule implementation according to task 3 requirements.
    
    Validates:
    - IoT Rule creation with correct name
    - MQTT topic pattern: device/+/data
    - SQL statement: SELECT *, timestamp() as received_at FROM 'device/+/data'
    - DynamoDB Put Item Action configuration
    - IAM role and permissions
    
    Requirements: 1.1, 1.4, 2.1, 2.3
    """
    app = core.App()
    stack = InfraStack(app, "test-iot-stack")
    template = assertions.Template.from_stack(stack)

    # Test IoT Rule exists with correct configuration
    template.has_resource_properties("AWS::IoT::TopicRule", {
        "RuleName": "WioTerminalSensorDataRule",
        "TopicRulePayload": {
            "Sql": "SELECT *, timestamp() as received_at FROM 'device/+/data'",
            "Description": "Process sensor data from WIO Terminal devices and store in DynamoDB",
            "RuleDisabled": False,
            "Actions": [
                {
                    "DynamoDB": {
                        "TableName": {"Ref": assertions.Match.any_value()},
                        "HashKeyField": "device_id",
                        "HashKeyValue": "${topic(2)}",  # Extract device_id from topic
                        "RangeKeyField": "timestamp", 
                        "RangeKeyValue": "${timestamp}",
                        "PayloadField": "data",
                        "RoleArn": {"Fn::GetAtt": [assertions.Match.any_value(), "Arn"]}
                    }
                }
            ],
            "ErrorAction": {
                "CloudwatchLogs": {
                    "LogGroupName": "/aws/iot/rule/WioTerminalSensorDataRule/errors",
                    "RoleArn": {"Fn::GetAtt": [assertions.Match.any_value(), "Arn"]}
                }
            }
        }
    })

    # Test IAM role for IoT Rule exists
    template.has_resource_properties("AWS::IAM::Role", {
        "AssumeRolePolicyDocument": {
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "iot.amazonaws.com"
                    },
                    "Action": "sts:AssumeRole"
                }
            ],
            "Version": "2012-10-17"
        },
        "Description": "IAM role for IoT Rule to write sensor data to DynamoDB"
    })

    # Test IAM policy for DynamoDB write permissions
    template.has_resource_properties("AWS::IAM::Policy", {
        "PolicyDocument": {
            "Statement": assertions.Match.array_with([
                {
                    "Effect": "Allow",
                    "Action": [
                        "dynamodb:BatchWriteItem",
                        "dynamodb:PutItem",
                        "dynamodb:UpdateItem",
                        "dynamodb:DeleteItem",
                        "dynamodb:DescribeTable"
                    ],
                    "Resource": [
                        {"Fn::GetAtt": [assertions.Match.any_value(), "Arn"]},
                        {"Ref": "AWS::NoValue"}
                    ]
                }
            ])
        }
    })

    # Test CloudWatch Logs group for error handling
    template.has_resource_properties("AWS::Logs::LogGroup", {
        "LogGroupName": "/aws/iot/rule/WioTerminalSensorDataRule/errors"
    })


def test_iot_rule_sql_statement_correctness():
    """
    Test that the IoT Rule SQL statement matches exactly the specification.
    
    Requirements: 1.1, 2.1
    """
    app = core.App()
    stack = InfraStack(app, "test-sql-stack")
    template = assertions.Template.from_stack(stack)
    
    # Get the template as dict to inspect the exact SQL
    template_dict = template.to_json()
    
    # Find the IoT Rule resource
    iot_rules = {k: v for k, v in template_dict.get('Resources', {}).items() 
                 if v.get('Type') == 'AWS::IoT::TopicRule'}
    
    assert len(iot_rules) == 1, "Expected exactly one IoT Rule"
    
    rule_name, rule_config = next(iter(iot_rules.items()))
    sql_statement = rule_config["Properties"]["TopicRulePayload"]["Sql"]
    
    # Verify exact SQL statement as specified in task
    expected_sql = "SELECT *, timestamp() as received_at FROM 'device/+/data'"
    assert sql_statement == expected_sql, f"SQL statement mismatch. Expected: {expected_sql}, Got: {sql_statement}"


def test_iot_rule_dynamodb_action_configuration():
    """
    Test that the DynamoDB action is correctly configured for the IoT Rule.
    
    Requirements: 1.4, 2.3
    """
    app = core.App()
    stack = InfraStack(app, "test-dynamo-action-stack")
    template = assertions.Template.from_stack(stack)
    
    template_dict = template.to_json()
    
    # Find the IoT Rule and verify DynamoDB action
    iot_rules = {k: v for k, v in template_dict.get('Resources', {}).items() 
                 if v.get('Type') == 'AWS::IoT::TopicRule'}
    
    rule_name, rule_config = next(iter(iot_rules.items()))
    actions = rule_config["Properties"]["TopicRulePayload"]["Actions"]
    
    assert len(actions) == 1, "Expected exactly one action"
    
    dynamo_action = actions[0]["DynamoDB"]
    
    # Verify DynamoDB action configuration
    assert dynamo_action["HashKeyField"] == "device_id"
    assert dynamo_action["HashKeyValue"] == "${topic(2)}"  # Extract from MQTT topic
    assert dynamo_action["RangeKeyField"] == "timestamp"
    assert dynamo_action["RangeKeyValue"] == "${timestamp}"
    assert dynamo_action["PayloadField"] == "data"
    
    # Verify role ARN reference
    assert "RoleArn" in dynamo_action
    assert "Fn::GetAtt" in dynamo_action["RoleArn"]


def test_mqtt_topic_pattern_validation():
    """
    Test that the MQTT topic pattern 'device/+/data' is correctly used in the SQL statement.
    
    Requirements: 1.1
    """
    app = core.App()
    stack = InfraStack(app, "test-topic-pattern-stack")
    template = assertions.Template.from_stack(stack)
    
    template_dict = template.to_json()
    
    # Find the IoT Rule and check topic pattern
    iot_rules = {k: v for k, v in template_dict.get('Resources', {}).items() 
                 if v.get('Type') == 'AWS::IoT::TopicRule'}
    
    rule_name, rule_config = next(iter(iot_rules.items()))
    sql_statement = rule_config["Properties"]["TopicRulePayload"]["Sql"]
    
    # Verify the topic pattern is used in the FROM clause
    assert "'device/+/data'" in sql_statement, "MQTT topic pattern 'device/+/data' not found in SQL statement"
    
    # Verify topic extraction for device_id
    actions = rule_config["Properties"]["TopicRulePayload"]["Actions"]
    dynamo_action = actions[0]["DynamoDB"]
    
    # ${topic(2)} extracts the device_id from device/{device_id}/data
    assert dynamo_action["HashKeyValue"] == "${topic(2)}", "Device ID extraction from topic not configured correctly"


def test_glue_crawler_implementation():
    """
    Test AWS Glue Crawler implementation according to task 6 requirements.
    
    Validates:
    - Glue Database creation for Data Catalog
    - Glue Crawler targeting DynamoDB table
    - Daily execution schedule (cron expression)
    - IAM role and permissions for Glue Crawler
    
    Requirements: 4.1, 4.2
    """
    app = core.App()
    stack = InfraStack(app, "test-glue-crawler-stack")
    template = assertions.Template.from_stack(stack)

    # Test Glue Database exists
    template.has_resource_properties("AWS::Glue::Database", {
        "DatabaseInput": {
            "Name": "wio-terminal-sensor-database",
            "Description": "Database for WIO Terminal sensor data metadata"
        }
    })

    # Test Glue Crawler exists with correct configuration
    template.has_resource_properties("AWS::Glue::Crawler", {
        "Name": "wio-terminal-sensor-data-crawler",
        "Description": "Crawler for WIO Terminal sensor data DynamoDB table",
        "DatabaseName": {"Ref": assertions.Match.any_value()},
        "Role": {"Fn::GetAtt": [assertions.Match.any_value(), "Arn"]},
        "Targets": {
            "DynamoDBTargets": [
                {
                    "Path": {"Ref": assertions.Match.any_value()}  # DynamoDB table name
                }
            ]
        },
        "Schedule": {
            "ScheduleExpression": "cron(0 2 * * ? *)"  # Daily at 2 AM UTC
        },
        "SchemaChangePolicy": {
            "UpdateBehavior": "UPDATE_IN_DATABASE",
            "DeleteBehavior": "LOG"
        }
    })

    # Test IAM role for Glue Crawler exists
    template.has_resource_properties("AWS::IAM::Role", {
        "AssumeRolePolicyDocument": {
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "glue.amazonaws.com"
                    },
                    "Action": "sts:AssumeRole"
                }
            ],
            "Version": "2012-10-17"
        },
        "Description": "IAM role for Glue Crawler to access DynamoDB and Data Catalog",
        "ManagedPolicyArns": [
            {"Fn::Join": ["", ["arn:", {"Ref": "AWS::Partition"}, ":iam::aws:policy/service-role/AWSGlueServiceRole"]]}
        ]
    })

    # Test IAM policy for DynamoDB read permissions
    template.has_resource_properties("AWS::IAM::Policy", {
        "PolicyDocument": {
            "Statement": assertions.Match.array_with([
                {
                    "Effect": "Allow",
                    "Action": [
                        "dynamodb:BatchGetItem",
                        "dynamodb:GetRecords",
                        "dynamodb:GetShardIterator",
                        "dynamodb:Query",
                        "dynamodb:GetItem",
                        "dynamodb:Scan",
                        "dynamodb:ConditionCheckItem",
                        "dynamodb:DescribeTable"
                    ],
                    "Resource": [
                        {"Fn::GetAtt": [assertions.Match.any_value(), "Arn"]},
                        {"Ref": "AWS::NoValue"}
                    ]
                }
            ])
        }
    })


def test_glue_crawler_schedule_configuration():
    """
    Test that the Glue Crawler is configured with daily execution schedule.
    
    Requirements: 4.1, 4.2
    """
    app = core.App()
    stack = InfraStack(app, "test-crawler-schedule-stack")
    template = assertions.Template.from_stack(stack)
    
    template_dict = template.to_json()
    
    # Find the Glue Crawler and verify schedule
    glue_crawlers = {k: v for k, v in template_dict.get('Resources', {}).items() 
                     if v.get('Type') == 'AWS::Glue::Crawler'}
    
    assert len(glue_crawlers) == 1, "Expected exactly one Glue Crawler"
    
    crawler_name, crawler_config = next(iter(glue_crawlers.items()))
    schedule = crawler_config["Properties"]["Schedule"]["ScheduleExpression"]
    
    # Verify daily schedule (cron expression for 2 AM UTC daily)
    expected_schedule = "cron(0 2 * * ? *)"
    assert schedule == expected_schedule, f"Schedule mismatch. Expected: {expected_schedule}, Got: {schedule}"


def test_glue_crawler_dynamodb_target():
    """
    Test that the Glue Crawler correctly targets the DynamoDB table.
    
    Requirements: 4.1, 4.2
    """
    app = core.App()
    stack = InfraStack(app, "test-crawler-target-stack")
    template = assertions.Template.from_stack(stack)
    
    template_dict = template.to_json()
    
    # Find the Glue Crawler and verify DynamoDB target
    glue_crawlers = {k: v for k, v in template_dict.get('Resources', {}).items() 
                     if v.get('Type') == 'AWS::Glue::Crawler'}
    
    crawler_name, crawler_config = next(iter(glue_crawlers.items()))
    targets = crawler_config["Properties"]["Targets"]
    
    # Verify DynamoDB target configuration
    assert "DynamoDBTargets" in targets, "DynamoDB targets not configured"
    dynamo_targets = targets["DynamoDBTargets"]
    assert len(dynamo_targets) == 1, "Expected exactly one DynamoDB target"
    
    # Verify the target references the DynamoDB table
    target_path = dynamo_targets[0]["Path"]
    assert "Ref" in target_path, "DynamoDB table reference not found in crawler target"


def test_athena_dynamodb_connector_implementation():
    """
    Test Athena DynamoDB Connector implementation according to task 7 requirements.
    
    Validates:
    - S3 bucket for Athena query results
    - S3 bucket for Athena spill data
    - Athena DynamoDB Connector from Serverless Application Repository
    - Athena WorkGroup configuration
    - Athena Data Catalog for DynamoDB
    
    Requirements: 4.1, 4.2
    """
    app = core.App()
    stack = InfraStack(app, "test-athena-connector-stack")
    template = assertions.Template.from_stack(stack)

    # Test S3 bucket for Athena query results exists
    template.has_resource_properties("AWS::S3::Bucket", {
        "BucketEncryption": {
            "ServerSideEncryptionConfiguration": [
                {
                    "ServerSideEncryptionByDefault": {
                        "SSEAlgorithm": "AES256"
                    }
                }
            ]
        },
        "PublicAccessBlockConfiguration": {
            "BlockPublicAcls": True,
            "BlockPublicPolicy": True,
            "IgnorePublicAcls": True,
            "RestrictPublicBuckets": True
        }
    })

    # Test Athena DynamoDB Connector from SAR exists
    template.has_resource_properties("AWS::Serverless::Application", {
        "Location": {
            "ApplicationId": "arn:aws:serverlessrepo:us-east-1:292517598671:applications/AthenaDynamoDBConnector",
            "SemanticVersion": "2022.47.1"
        },
        "Parameters": {
            "AthenaCatalogName": "wio-terminal-dynamodb-catalog",
            "SpillBucket": assertions.Match.any_value(),
            "LambdaMemory": "3008",
            "LambdaTimeout": "900",
            "DisableSpillEncryption": "false"
        }
    })

    # Test Athena WorkGroup exists
    template.has_resource_properties("AWS::Athena::WorkGroup", {
        "Name": "wio-terminal-sensor-workgroup",
        "Description": "WorkGroup for querying WIO Terminal sensor data",
        "WorkGroupConfiguration": {
            "ResultConfiguration": {
                "OutputLocation": assertions.Match.any_value(),
                "EncryptionConfiguration": {
                    "EncryptionOption": "SSE_S3"
                }
            },
            "EnforceWorkGroupConfiguration": True,
            "PublishCloudWatchMetricsEnabled": True
        }
    })

    # Test Athena Data Catalog exists
    template.has_resource_properties("AWS::Athena::DataCatalog", {
        "Name": "wio-terminal-dynamodb-catalog",
        "Type": "LAMBDA",
        "Description": "Athena Data Catalog for DynamoDB sensor data",
        "Parameters": assertions.Match.object_like({
            "metadata-function": assertions.Match.any_value()
        })
    })


def test_athena_s3_buckets_configuration():
    """
    Test that S3 buckets for Athena are correctly configured with encryption and security.
    
    Requirements: 4.1, 4.2
    """
    app = core.App()
    stack = InfraStack(app, "test-athena-s3-stack")
    template = assertions.Template.from_stack(stack)
    
    template_dict = template.to_json()
    
    # Find all S3 buckets
    s3_buckets = {k: v for k, v in template_dict.get('Resources', {}).items() 
                  if v.get('Type') == 'AWS::S3::Bucket'}
    
    # Should have at least 2 buckets (query results and spill)
    assert len(s3_buckets) >= 2, f"Expected at least 2 S3 buckets, found {len(s3_buckets)}"
    
    # Verify all buckets have encryption enabled
    for bucket_name, bucket_config in s3_buckets.items():
        props = bucket_config["Properties"]
        assert "BucketEncryption" in props, f"Bucket {bucket_name} missing encryption configuration"
        
        encryption_config = props["BucketEncryption"]["ServerSideEncryptionConfiguration"]
        assert len(encryption_config) > 0, f"Bucket {bucket_name} has empty encryption configuration"
        assert encryption_config[0]["ServerSideEncryptionByDefault"]["SSEAlgorithm"] == "AES256"
        
        # Verify public access is blocked
        assert "PublicAccessBlockConfiguration" in props, f"Bucket {bucket_name} missing public access block"
        public_access = props["PublicAccessBlockConfiguration"]
        assert public_access["BlockPublicAcls"] == True
        assert public_access["BlockPublicPolicy"] == True
        assert public_access["IgnorePublicAcls"] == True
        assert public_access["RestrictPublicBuckets"] == True


def test_athena_connector_parameters():
    """
    Test that the Athena DynamoDB Connector is configured with correct parameters.
    
    Requirements: 4.1, 4.2
    """
    app = core.App()
    stack = InfraStack(app, "test-connector-params-stack")
    template = assertions.Template.from_stack(stack)
    
    template_dict = template.to_json()
    
    # Find the SAR application
    sar_apps = {k: v for k, v in template_dict.get('Resources', {}).items() 
                if v.get('Type') == 'AWS::Serverless::Application'}
    
    assert len(sar_apps) == 1, "Expected exactly one Serverless Application"
    
    app_name, app_config = next(iter(sar_apps.items()))
    parameters = app_config["Properties"]["Parameters"]
    
    # Verify connector parameters
    assert parameters["AthenaCatalogName"] == "wio-terminal-dynamodb-catalog"
    assert parameters["LambdaMemory"] == "3008"
    assert parameters["LambdaTimeout"] == "900"
    assert parameters["DisableSpillEncryption"] == "false"
    assert "SpillBucket" in parameters


def test_athena_workgroup_output_location():
    """
    Test that the Athena WorkGroup is configured with correct S3 output location.
    
    Requirements: 4.1, 4.2
    """
    app = core.App()
    stack = InfraStack(app, "test-workgroup-output-stack")
    template = assertions.Template.from_stack(stack)
    
    template_dict = template.to_json()
    
    # Find the Athena WorkGroup
    workgroups = {k: v for k, v in template_dict.get('Resources', {}).items() 
                  if v.get('Type') == 'AWS::Athena::WorkGroup'}
    
    assert len(workgroups) == 1, "Expected exactly one Athena WorkGroup"
    
    wg_name, wg_config = next(iter(workgroups.items()))
    result_config = wg_config["Properties"]["WorkGroupConfiguration"]["ResultConfiguration"]
    
    # Verify output location is configured
    assert "OutputLocation" in result_config
    output_location = result_config["OutputLocation"]
    
    # Should be an S3 path (either direct string or Fn::Join)
    assert output_location is not None
    
    # Verify encryption is enabled
    assert "EncryptionConfiguration" in result_config
    assert result_config["EncryptionConfiguration"]["EncryptionOption"] == "SSE_S3"


def test_quicksight_data_source_implementation():
    """
    Test QuickSight data source implementation according to task 8 requirements.
    
    Validates:
    - QuickSight data source configured with Athena
    - Data source references the Athena WorkGroup
    - Proper permissions configuration
    
    Requirements: 4.1, 4.3, 4.4, 4.5
    """
    app = core.App()
    stack = InfraStack(app, "test-quicksight-stack")
    template = assertions.Template.from_stack(stack)

    # Test QuickSight Data Source exists
    template.has_resource_properties("AWS::QuickSight::DataSource", {
        "DataSourceId": "wio-terminal-athena-datasource",
        "Name": "WioTerminalSensorData",
        "Type": "ATHENA",
        "DataSourceParameters": {
            "AthenaParameters": {
                "WorkGroup": assertions.Match.any_value()
            }
        }
    })


def test_quicksight_athena_integration():
    """
    Test that QuickSight data source correctly integrates with Athena WorkGroup.
    
    Requirements: 4.1, 4.3
    """
    app = core.App()
    stack = InfraStack(app, "test-qs-athena-integration-stack")
    template = assertions.Template.from_stack(stack)
    
    template_dict = template.to_json()
    
    # Find QuickSight data source
    qs_datasources = {k: v for k, v in template_dict.get('Resources', {}).items() 
                      if v.get('Type') == 'AWS::QuickSight::DataSource'}
    
    assert len(qs_datasources) == 1, "Expected exactly one QuickSight data source"
    
    ds_name, ds_config = next(iter(qs_datasources.items()))
    
    # Verify Athena parameters
    athena_params = ds_config["Properties"]["DataSourceParameters"]["AthenaParameters"]
    assert "WorkGroup" in athena_params, "WorkGroup not configured in Athena parameters"
    
    # Verify data source type is ATHENA
    assert ds_config["Properties"]["Type"] == "ATHENA"
    
    # Verify data source has a name
    assert ds_config["Properties"]["Name"] == "WioTerminalSensorData"


def test_quicksight_permissions_configuration():
    """
    Test that QuickSight data source has proper permissions configured.
    
    Requirements: 4.1, 4.4, 4.5
    """
    app = core.App()
    stack = InfraStack(app, "test-qs-permissions-stack")
    template = assertions.Template.from_stack(stack)
    
    template_dict = template.to_json()
    
    # Find QuickSight data source
    qs_datasources = {k: v for k, v in template_dict.get('Resources', {}).items() 
                      if v.get('Type') == 'AWS::QuickSight::DataSource'}
    
    ds_name, ds_config = next(iter(qs_datasources.items()))
    
    # Verify permissions are configured
    assert "Permissions" in ds_config["Properties"], "Permissions not configured"
    permissions = ds_config["Properties"]["Permissions"]
    
    assert len(permissions) > 0, "No permissions defined"
    
    # Verify permission structure
    permission = permissions[0]
    assert "Principal" in permission, "Principal not defined in permission"
    assert "Actions" in permission, "Actions not defined in permission"
    
    # Verify essential QuickSight actions are included
    actions = permission["Actions"]
    essential_actions = [
        "quicksight:DescribeDataSource",
        "quicksight:PassDataSource"
    ]
    
    for action in essential_actions:
        assert action in actions, f"Essential action {action} not found in permissions"


