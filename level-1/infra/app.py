#!/usr/bin/env python3
import os

import aws_cdk as cdk

from infra.infra_stack import InfraStack


app = cdk.App()
InfraStack(app, "attempt-iot-monitoring-stack",
    # Specify the AWS Account and Region from the current CLI configuration
    # This is required for resources that need account/region information (e.g., S3 bucket names)
    env=cdk.Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=os.getenv('CDK_DEFAULT_REGION')),

    # For more information, see https://docs.aws.amazon.com/cdk/latest/guide/environments.html
    )

app.synth()
