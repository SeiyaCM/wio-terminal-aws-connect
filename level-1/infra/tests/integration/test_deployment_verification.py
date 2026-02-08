"""
Integration tests for CDK deployment verification.

This module tests the complete infrastructure deployment and validates
that all components are correctly configured for end-to-end data flow.

Requirements: 5.4
"""

import aws_cdk as core
import aws_cdk.assertions as assertions
from infra.infra_stack import InfraStack


def test_complete_stack_synthesis():
    """
    Test that the complete CDK stack can be synthesized without errors.
    
    This validates that all resources are correctly defined and there are
    no circular dependencies or configuration errors.
    
    Requirements: 5.4
    """
    app = core.App()
    stack = InfraStack(app, "integration-test-stack")
    
    # Synthesize the stack - this will fail if there are any errors
    template = assertions.Template.from_stack(stack)
    
    # Verify template is not empty
    template_dict = template.to_json()
    assert "Resources" in template_dict
    assert len(template_dict["Resources"]) > 0


def test_end_to_end_data_flow_resources():
    """
    Test that all resources required for end-to-end data flow are present.
    
    Validates the complete data pipeline:
    IoT Core → IoT Rule → DynamoDB → Glue Crawler → Athena → QuickSight
    
    Requirements: 5.4
    """
    app = core.App()
    stack = InfraStack(app, "e2e-test-stack")
    template = assertions.Template.from_stack(stack)
    
    # Verify IoT Core resources
    template.resource_count_is("AWS::IoT::TopicRule", 1)
    
    # Verify DynamoDB table
    template.resource_count_is("AWS::DynamoDB::Table", 1)
    
    # Verify Glue resources
    template.resource_count_is("AWS::Glue::Database", 1)
    template.resource_count_is("AWS::Glue::Crawler", 1)
    
    # Verify Athena resources
    template.resource_count_is("AWS::Athena::WorkGroup", 1)
    template.resource_count_is("AWS::Athena::DataCatalog", 1)
    
    # Verify S3 buckets (at least 2: query results and spill)
    s3_bucket_count = len([
        r for r in template.to_json()["Resources"].values()
        if r["Type"] == "AWS::S3::Bucket"
    ])
    assert s3_bucket_count >= 2, f"Expected at least 2 S3 buckets, found {s3_bucket_count}"
    
    # Verify QuickSight data source
    template.resource_count_is("AWS::QuickSight::DataSource", 1)
    
    # Verify Serverless Application (Athena DynamoDB Connector)
    template.resource_count_is("AWS::Serverless::Application", 1)


def test_iam_roles_and_permissions():
    """
    Test that all required IAM roles and permissions are correctly configured.
    
    Validates:
    - IoT Rule role with DynamoDB write permissions
    - Glue Crawler role with DynamoDB read permissions
    - Proper trust relationships
    
    Requirements: 5.4
    """
    app = core.App()
    stack = InfraStack(app, "iam-test-stack")
    template = assertions.Template.from_stack(stack)
    
    # Count IAM roles (IoT Rule role + Glue Crawler role)
    iam_role_count = len([
        r for r in template.to_json()["Resources"].values()
        if r["Type"] == "AWS::IAM::Role"
    ])
    assert iam_role_count >= 2, f"Expected at least 2 IAM roles, found {iam_role_count}"
    
    # Verify IoT service principal
    template.has_resource_properties("AWS::IAM::Role", {
        "AssumeRolePolicyDocument": {
            "Statement": assertions.Match.array_with([
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "iot.amazonaws.com"
                    },
                    "Action": "sts:AssumeRole"
                }
            ])
        }
    })
    
    # Verify Glue service principal
    template.has_resource_properties("AWS::IAM::Role", {
        "AssumeRolePolicyDocument": {
            "Statement": assertions.Match.array_with([
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "glue.amazonaws.com"
                    },
                    "Action": "sts:AssumeRole"
                }
            ])
        }
    })
    
    # Verify IAM policies exist
    iam_policy_count = len([
        r for r in template.to_json()["Resources"].values()
        if r["Type"] == "AWS::IAM::Policy"
    ])
    assert iam_policy_count >= 2, f"Expected at least 2 IAM policies, found {iam_policy_count}"


def test_resource_dependencies():
    """
    Test that resource dependencies are correctly configured.
    
    Validates that resources are created in the correct order to avoid
    deployment failures due to missing dependencies.
    
    Requirements: 5.4
    """
    app = core.App()
    stack = InfraStack(app, "dependency-test-stack")
    template = assertions.Template.from_stack(stack)
    
    template_dict = template.to_json()
    resources = template_dict["Resources"]
    
    # Find QuickSight data source
    qs_datasources = {k: v for k, v in resources.items() 
                      if v.get("Type") == "AWS::QuickSight::DataSource"}
    
    if qs_datasources:
        ds_name, ds_config = next(iter(qs_datasources.items()))
        
        # Verify QuickSight has dependency on Athena WorkGroup
        assert "DependsOn" in ds_config, "QuickSight data source missing dependencies"
        depends_on = ds_config["DependsOn"]
        
        # Find Athena WorkGroup resource name
        athena_workgroups = [k for k, v in resources.items() 
                            if v.get("Type") == "AWS::Athena::WorkGroup"]
        
        assert len(athena_workgroups) > 0, "Athena WorkGroup not found"
        
        # Verify dependency exists
        if isinstance(depends_on, list):
            assert any(wg in depends_on for wg in athena_workgroups), \
                "QuickSight does not depend on Athena WorkGroup"
        else:
            assert depends_on in athena_workgroups, \
                "QuickSight does not depend on Athena WorkGroup"
    
    # Find Athena Data Catalog
    athena_catalogs = {k: v for k, v in resources.items() 
                       if v.get("Type") == "AWS::Athena::DataCatalog"}
    
    if athena_catalogs:
        catalog_name, catalog_config = next(iter(athena_catalogs.items()))
        
        # Verify Athena Data Catalog has dependency on SAR Application
        assert "DependsOn" in catalog_config, "Athena Data Catalog missing dependencies"
        depends_on = catalog_config["DependsOn"]
        
        # Find SAR Application resource name
        sar_apps = [k for k, v in resources.items() 
                   if v.get("Type") == "AWS::Serverless::Application"]
        
        assert len(sar_apps) > 0, "Serverless Application not found"
        
        # Verify dependency exists
        if isinstance(depends_on, list):
            assert any(app in depends_on for app in sar_apps), \
                "Athena Data Catalog does not depend on SAR Application"
        else:
            assert depends_on in sar_apps, \
                "Athena Data Catalog does not depend on SAR Application"


def test_stack_naming_convention():
    """
    Test that the stack follows the required naming convention.
    
    Requirements: 5.3
    """
    app = core.App()
    stack = InfraStack(app, "wio-terminal-infra-stack")
    
    # Verify stack name
    assert stack.stack_name == "wio-terminal-infra-stack", \
        f"Stack name mismatch. Expected: wio-terminal-infra-stack, Got: {stack.stack_name}"


def test_dynamodb_table_configuration():
    """
    Test that DynamoDB table is correctly configured for time-series data.
    
    Requirements: 3.1, 3.4, 5.4
    """
    app = core.App()
    stack = InfraStack(app, "dynamodb-config-test-stack")
    template = assertions.Template.from_stack(stack)
    
    # Verify DynamoDB table configuration
    template.has_resource_properties("AWS::DynamoDB::Table", {
        "TableName": "wio-terminal-sensor-data",
        "KeySchema": [
            {
                "AttributeName": "device_id",
                "KeyType": "HASH"
            },
            {
                "AttributeName": "timestamp",
                "KeyType": "RANGE"
            }
        ],
        "AttributeDefinitions": [
            {
                "AttributeName": "device_id",
                "AttributeType": "S"
            },
            {
                "AttributeName": "timestamp",
                "AttributeType": "N"
            }
        ],
        "BillingMode": "PAY_PER_REQUEST",
        "PointInTimeRecoverySpecification": {
            "PointInTimeRecoveryEnabled": True
        }
    })


def test_iot_rule_error_handling():
    """
    Test that IoT Rule has proper error handling configured.
    
    Requirements: 1.2, 5.4
    """
    app = core.App()
    stack = InfraStack(app, "error-handling-test-stack")
    template = assertions.Template.from_stack(stack)
    
    # Verify IoT Rule has error action
    template.has_resource_properties("AWS::IoT::TopicRule", {
        "TopicRulePayload": {
            "ErrorAction": {
                "CloudwatchLogs": {
                    "LogGroupName": "/aws/iot/rule/WioTerminalSensorDataRule/errors",
                    "RoleArn": assertions.Match.any_value()
                }
            }
        }
    })
    
    # Verify CloudWatch Log Group exists
    template.has_resource_properties("AWS::Logs::LogGroup", {
        "LogGroupName": "/aws/iot/rule/WioTerminalSensorDataRule/errors"
    })


def test_s3_bucket_security_configuration():
    """
    Test that S3 buckets have proper security configurations.
    
    Requirements: 5.4
    """
    app = core.App()
    stack = InfraStack(app, "s3-security-test-stack")
    template = assertions.Template.from_stack(stack)
    
    template_dict = template.to_json()
    
    # Find all S3 buckets
    s3_buckets = {k: v for k, v in template_dict["Resources"].items() 
                  if v.get("Type") == "AWS::S3::Bucket"}
    
    # Verify each bucket has proper security
    for bucket_name, bucket_config in s3_buckets.items():
        props = bucket_config["Properties"]
        
        # Verify encryption
        assert "BucketEncryption" in props, \
            f"Bucket {bucket_name} missing encryption"
        
        # Verify public access block
        assert "PublicAccessBlockConfiguration" in props, \
            f"Bucket {bucket_name} missing public access block"
        
        public_access = props["PublicAccessBlockConfiguration"]
        assert public_access["BlockPublicAcls"] == True
        assert public_access["BlockPublicPolicy"] == True
        assert public_access["IgnorePublicAcls"] == True
        assert public_access["RestrictPublicBuckets"] == True


def test_athena_connector_configuration():
    """
    Test that Athena DynamoDB Connector is properly configured.
    
    Requirements: 4.1, 4.2, 5.4
    """
    app = core.App()
    stack = InfraStack(app, "athena-connector-test-stack")
    template = assertions.Template.from_stack(stack)
    
    # Verify SAR application configuration
    template.has_resource_properties("AWS::Serverless::Application", {
        "Location": {
            "ApplicationId": "arn:aws:serverlessrepo:us-east-1:292517598671:applications/AthenaDynamoDBConnector",
            "SemanticVersion": "2022.47.1"
        },
        "Parameters": {
            "AthenaCatalogName": "wio-terminal-dynamodb-catalog",
            "LambdaMemory": "3008",
            "LambdaTimeout": "900",
            "DisableSpillEncryption": "false"
        }
    })


def test_complete_data_pipeline_integration():
    """
    Test that all components of the data pipeline are correctly integrated.
    
    This test validates the complete flow:
    1. IoT Rule receives data from MQTT topic
    2. IoT Rule writes to DynamoDB
    3. Glue Crawler catalogs DynamoDB metadata
    4. Athena can query DynamoDB via connector
    5. QuickSight can access data via Athena
    
    Requirements: 1.1, 2.1, 3.1, 4.1, 5.4
    """
    app = core.App()
    stack = InfraStack(app, "pipeline-integration-test-stack")
    template = assertions.Template.from_stack(stack)
    
    template_dict = template.to_json()
    resources = template_dict["Resources"]
    
    # Step 1: Verify IoT Rule exists and targets DynamoDB
    iot_rules = {k: v for k, v in resources.items() 
                 if v.get("Type") == "AWS::IoT::TopicRule"}
    assert len(iot_rules) == 1, "IoT Rule not found"
    
    rule_name, rule_config = next(iter(iot_rules.items()))
    actions = rule_config["Properties"]["TopicRulePayload"]["Actions"]
    assert len(actions) > 0, "IoT Rule has no actions"
    assert "DynamoDB" in actions[0], "IoT Rule does not target DynamoDB"
    
    # Step 2: Verify DynamoDB table exists
    dynamodb_tables = {k: v for k, v in resources.items() 
                       if v.get("Type") == "AWS::DynamoDB::Table"}
    assert len(dynamodb_tables) == 1, "DynamoDB table not found"
    
    # Step 3: Verify Glue Crawler targets DynamoDB
    glue_crawlers = {k: v for k, v in resources.items() 
                     if v.get("Type") == "AWS::Glue::Crawler"}
    assert len(glue_crawlers) == 1, "Glue Crawler not found"
    
    crawler_name, crawler_config = next(iter(glue_crawlers.items()))
    targets = crawler_config["Properties"]["Targets"]
    assert "DynamoDBTargets" in targets, "Glue Crawler does not target DynamoDB"
    
    # Step 4: Verify Athena connector and data catalog exist
    athena_catalogs = {k: v for k, v in resources.items() 
                       if v.get("Type") == "AWS::Athena::DataCatalog"}
    assert len(athena_catalogs) == 1, "Athena Data Catalog not found"
    
    sar_apps = {k: v for k, v in resources.items() 
                if v.get("Type") == "AWS::Serverless::Application"}
    assert len(sar_apps) == 1, "Athena DynamoDB Connector not found"
    
    # Step 5: Verify QuickSight data source uses Athena
    qs_datasources = {k: v for k, v in resources.items() 
                      if v.get("Type") == "AWS::QuickSight::DataSource"}
    assert len(qs_datasources) == 1, "QuickSight data source not found"
    
    ds_name, ds_config = next(iter(qs_datasources.items()))
    assert ds_config["Properties"]["Type"] == "ATHENA", \
        "QuickSight data source does not use Athena"


def test_resource_naming_consistency():
    """
    Test that all resources follow consistent naming conventions.
    
    Requirements: 5.4
    """
    app = core.App()
    stack = InfraStack(app, "naming-test-stack")
    template = assertions.Template.from_stack(stack)
    
    template_dict = template.to_json()
    resources = template_dict["Resources"]
    
    # Verify DynamoDB table name
    dynamodb_tables = {k: v for k, v in resources.items() 
                       if v.get("Type") == "AWS::DynamoDB::Table"}
    for table_name, table_config in dynamodb_tables.items():
        assert "wio-terminal" in table_config["Properties"]["TableName"].lower(), \
            "DynamoDB table name does not follow naming convention"
    
    # Verify IoT Rule name
    iot_rules = {k: v for k, v in resources.items() 
                 if v.get("Type") == "AWS::IoT::TopicRule"}
    for rule_name, rule_config in iot_rules.items():
        assert "WioTerminal" in rule_config["Properties"]["RuleName"], \
            "IoT Rule name does not follow naming convention"
    
    # Verify Glue Database name
    glue_databases = {k: v for k, v in resources.items() 
                      if v.get("Type") == "AWS::Glue::Database"}
    for db_name, db_config in glue_databases.items():
        db_input = db_config["Properties"]["DatabaseInput"]
        assert "wio-terminal" in db_input["Name"].lower(), \
            "Glue Database name does not follow naming convention"
    
    # Verify Athena WorkGroup name
    athena_workgroups = {k: v for k, v in resources.items() 
                         if v.get("Type") == "AWS::Athena::WorkGroup"}
    for wg_name, wg_config in athena_workgroups.items():
        assert "wio-terminal" in wg_config["Properties"]["Name"].lower(), \
            "Athena WorkGroup name does not follow naming convention"
