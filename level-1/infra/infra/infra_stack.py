from aws_cdk import (
    Stack,
    aws_dynamodb as dynamodb,
    aws_iot as iot,
    aws_iam as iam,
    aws_glue as glue,
    aws_s3 as s3,
    aws_logs as logs,
    aws_sam as sam,
    aws_athena as athena,
    aws_quicksight as quicksight,
    RemovalPolicy,
)
from constructs import Construct

class InfraStack(Stack):
    """
    IoT AWS Infrastructure Stack for WIO Terminal monitoring system.
    
    This stack creates:
    - DynamoDB table for time-series data storage
    - IoT Core and IoT Rules for data processing
    - IAM roles and permissions
    - AWS Glue Crawler for metadata management
    - S3 buckets for Athena query results and spill data
    - Athena DynamoDB Connector for querying DynamoDB data
    - QuickSight data source for visualization
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # DynamoDB table for time-series data storage
        self.sensor_data_table = dynamodb.Table(
            self, "SensorDataTable",
            table_name="wio-terminal-sensor-data",
            partition_key=dynamodb.Attribute(
                name="device_id",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.NUMBER
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,  # For development/testing
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            ),
        )

        # IAM role for IoT Rule to write to DynamoDB
        self.iot_rule_role = iam.Role(
            self, "IoTRuleRole",
            assumed_by=iam.ServicePrincipal("iot.amazonaws.com"),
            description="IAM role for IoT Rule to write sensor data to DynamoDB",
        )

        # Grant DynamoDB write permissions to IoT Rule role
        self.sensor_data_table.grant_write_data(self.iot_rule_role)

        # Grant CloudWatch Logs permissions for error logging
        self.iot_rule_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                resources=["arn:aws:logs:*:*:log-group:/aws/iot/rule/WioTerminalSensorDataRule/*"]
            )
        )

        # CloudWatch Log Group for IoT Rule errors
        self.iot_rule_log_group = logs.LogGroup(
            self, "IoTRuleLogGroup",
            log_group_name="/aws/iot/rule/WioTerminalSensorDataRule/errors",
            removal_policy=RemovalPolicy.DESTROY
        )

        # IoT Rule for processing sensor data and writing to DynamoDB
        self.sensor_data_rule = iot.CfnTopicRule(
            self, "SensorDataRule",
            rule_name="WioTerminalSensorDataRule",
            topic_rule_payload=iot.CfnTopicRule.TopicRulePayloadProperty(
                sql="SELECT *, timestamp() as received_at FROM 'device/+/data'",
                description="Process sensor data from WIO Terminal devices and store in DynamoDB",
                rule_disabled=False,
                actions=[
                    iot.CfnTopicRule.ActionProperty(
                        dynamo_db=iot.CfnTopicRule.DynamoDBActionProperty(
                            table_name=self.sensor_data_table.table_name,
                            role_arn=self.iot_rule_role.role_arn,
                            hash_key_field="device_id",
                            hash_key_value="${topic(2)}",  # Extract device_id from topic
                            range_key_field="timestamp",
                            range_key_value="${timestamp}",
                            payload_field="data"
                        )
                    )
                ],
                error_action=iot.CfnTopicRule.ActionProperty(
                    cloudwatch_logs=iot.CfnTopicRule.CloudwatchLogsActionProperty(
                        log_group_name="/aws/iot/rule/WioTerminalSensorDataRule/errors",
                        role_arn=self.iot_rule_role.role_arn
                    )
                )
            )
        )

        # Glue Database for Data Catalog
        self.glue_database = glue.CfnDatabase(
            self, "SensorDataDatabase",
            catalog_id=self.account,
            database_input=glue.CfnDatabase.DatabaseInputProperty(
                name="wio-terminal-sensor-database",
                description="Database for WIO Terminal sensor data metadata"
            )
        )

        # IAM role for Glue Crawler
        self.glue_crawler_role = iam.Role(
            self, "GlueCrawlerRole",
            assumed_by=iam.ServicePrincipal("glue.amazonaws.com"),
            description="IAM role for Glue Crawler to access DynamoDB and Data Catalog",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSGlueServiceRole")
            ]
        )

        # Grant DynamoDB read permissions to Glue Crawler role
        self.sensor_data_table.grant_read_data(self.glue_crawler_role)

        # AWS Glue Crawler for DynamoDB table metadata
        self.sensor_data_crawler = glue.CfnCrawler(
            self, "SensorDataCrawler",
            name="wio-terminal-sensor-data-crawler",
            role=self.glue_crawler_role.role_arn,
            database_name=self.glue_database.ref,
            description="Crawler for WIO Terminal sensor data DynamoDB table",
            targets=glue.CfnCrawler.TargetsProperty(
                dynamo_db_targets=[
                    glue.CfnCrawler.DynamoDBTargetProperty(
                        path=self.sensor_data_table.table_name
                    )
                ]
            ),
            schedule=glue.CfnCrawler.ScheduleProperty(
                schedule_expression="cron(0 2 * * ? *)"  # Daily at 2 AM UTC
            ),
            schema_change_policy=glue.CfnCrawler.SchemaChangePolicyProperty(
                update_behavior="UPDATE_IN_DATABASE",
                delete_behavior="LOG"
            ),
            configuration='{"Version":1.0,"CrawlerOutput":{"Partitions":{"AddOrUpdateBehavior":"InheritFromTable"},"Tables":{"AddOrUpdateBehavior":"MergeNewColumns"}}}'
        )

        # S3 bucket for Athena query results
        self.athena_query_results_bucket = s3.Bucket(
            self, "AthenaQueryResultsBucket",
            bucket_name=f"wio-terminal-athena-results-{self.account}-{self.region}",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            versioned=False,
        )

        # S3 bucket for Athena DynamoDB Connector spill data
        self.athena_spill_bucket = s3.Bucket(
            self, "AthenaSpillBucket",
            bucket_name=f"wio-terminal-athena-spill-{self.account}-{self.region}",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            versioned=False,
        )

        # Deploy Athena DynamoDB Connector from Serverless Application Repository
        self.athena_dynamodb_connector = sam.CfnApplication(
            self, "AthenaDynamoDBConnector",
            location=sam.CfnApplication.ApplicationLocationProperty(
                application_id="arn:aws:serverlessrepo:us-east-1:292517598671:applications/AthenaDynamoDBConnector",
                semantic_version="2022.47.1"
            ),
            parameters={
                "AthenaCatalogName": "wio-terminal-dynamodb-catalog",
                "SpillBucket": self.athena_spill_bucket.bucket_name,
                "LambdaMemory": "3008",
                "LambdaTimeout": "900",
                "DisableSpillEncryption": "false"
            }
        )

        # Athena WorkGroup for sensor data queries
        self.athena_workgroup = athena.CfnWorkGroup(
            self, "SensorDataWorkGroup",
            name="wio-terminal-sensor-workgroup",
            description="WorkGroup for querying WIO Terminal sensor data",
            work_group_configuration=athena.CfnWorkGroup.WorkGroupConfigurationProperty(
                result_configuration=athena.CfnWorkGroup.ResultConfigurationProperty(
                    output_location=f"s3://{self.athena_query_results_bucket.bucket_name}/",
                    encryption_configuration=athena.CfnWorkGroup.EncryptionConfigurationProperty(
                        encryption_option="SSE_S3"
                    )
                ),
                enforce_work_group_configuration=True,
                publish_cloud_watch_metrics_enabled=True
            )
        )

        # Athena Data Catalog for DynamoDB
        self.athena_data_catalog = athena.CfnDataCatalog(
            self, "DynamoDBDataCatalog",
            name="wio-terminal-dynamodb-catalog",
            type="LAMBDA",
            description="Athena Data Catalog for DynamoDB sensor data",
            parameters={
                "metadata-function": f"arn:aws:lambda:{self.region}:{self.account}:function:wio-terminal-dynamodb-catalog"
            }
        )

        # Add dependency to ensure connector is deployed before data catalog
        self.athena_data_catalog.add_dependency(self.athena_dynamodb_connector)

        # QuickSight Data Source for Athena
        # Note: QuickSight requires manual setup for the first time (user/group creation)
        # This creates the data source configuration that can be used in QuickSight dashboards
        self.quicksight_data_source = quicksight.CfnDataSource(
            self, "QuickSightAthenaDataSource",
            data_source_id="wio-terminal-athena-datasource",
            name="WioTerminalSensorData",
            type="ATHENA",
            aws_account_id=self.account,
            data_source_parameters=quicksight.CfnDataSource.DataSourceParametersProperty(
                athena_parameters=quicksight.CfnDataSource.AthenaParametersProperty(
                    work_group=self.athena_workgroup.name
                )
            ),
            permissions=[
                quicksight.CfnDataSource.ResourcePermissionProperty(
                    principal=f"arn:aws:quicksight:{self.region}:{self.account}:user/default/Admin",
                    actions=[
                        "quicksight:DescribeDataSource",
                        "quicksight:DescribeDataSourcePermissions",
                        "quicksight:PassDataSource",
                        "quicksight:UpdateDataSource",
                        "quicksight:DeleteDataSource",
                        "quicksight:UpdateDataSourcePermissions"
                    ]
                )
            ]
        )

        # Add dependency to ensure Athena workgroup is created first
        self.quicksight_data_source.add_dependency(self.athena_workgroup)
