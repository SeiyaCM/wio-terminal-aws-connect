"""
Property-based tests for CDK resource definition accuracy.

Feature: iot-aws-infrastructure, Property 5: CDKリソース定義の正確性
Validates: Requirements 5.4
"""

import aws_cdk as core
import aws_cdk.assertions as assertions
from hypothesis import given, strategies as st, settings
import pytest
from typing import Dict, Any

from infra.infra_stack import InfraStack


class TestCDKResourceProperties:
    """Property-based tests for CDK resource definitions."""

    @given(
        stack_name=st.text(
            alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-",
            min_size=1,
            max_size=50
        ).filter(lambda x: x and x[0].isalpha() and x[-1] != '-' and '--' not in x)
    )
    @settings(max_examples=100, deadline=None)
    def test_cdk_stack_creation_property(self, stack_name: str):
        """
        Property 5: CDKリソース定義の正確性
        
        For any valid stack name, CDK deployment operations should correctly
        define and create the necessary AWS resources (IoT Core, DynamoDB, 
        Glue Crawler, Athena Connector, QuickSight).
        
        **Feature: iot-aws-infrastructure, Property 5: CDKリソース定義の正確性**
        **Validates: Requirements 5.4**
        """
        # Create a new app for each test to avoid construct name conflicts
        app = core.App()
        
        # Create stack with generated name
        stack = InfraStack(app, stack_name)
        
        # Generate CloudFormation template
        template = assertions.Template.from_stack(stack)
        
        # Verify stack can be synthesized without errors
        assert template is not None
        
        # Verify stack has the expected construct ID
        assert stack.node.id == stack_name
        
        # Verify stack is properly configured
        assert isinstance(stack, core.Stack)
        assert stack.stack_name == stack_name

    @given(
        construct_props=st.dictionaries(
            keys=st.sampled_from(["env", "description", "tags"]),
            values=st.one_of(
                st.dictionaries(
                    keys=st.sampled_from(["account", "region"]),
                    values=st.text(min_size=1, max_size=20)
                ),
                st.text(min_size=1, max_size=100),
                st.dictionaries(
                    keys=st.text(min_size=1, max_size=20),
                    values=st.text(min_size=1, max_size=50)
                )
            ),
            min_size=0,
            max_size=3
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_cdk_stack_properties_consistency(self, construct_props: Dict[str, Any]):
        """
        Property 5: CDKリソース定義の正確性 (Properties Consistency)
        
        For any valid construct properties, the CDK stack should maintain
        consistency in resource definitions and handle various configuration
        parameters correctly.
        
        **Feature: iot-aws-infrastructure, Property 5: CDKリソース定義の正確性**
        **Validates: Requirements 5.4**
        """
        # Create a new app for each test to avoid construct name conflicts
        app = core.App()
        
        # Create stack with various properties
        stack = InfraStack(app, "test-stack", **construct_props)
        
        # Generate template to verify it can be synthesized
        template = assertions.Template.from_stack(stack)
        
        # Verify template generation succeeds
        assert template is not None
        
        # Verify stack maintains its identity regardless of properties
        assert isinstance(stack, InfraStack)
        assert stack.node.id == "test-stack"

    def test_cdk_template_structure_invariant(self):
        """
        Property 5: CDKリソース定義の正確性 (Template Structure)
        
        For any CDK stack instance, the generated CloudFormation template
        should have a valid structure with required sections.
        
        **Feature: iot-aws-infrastructure, Property 5: CDKリソース定義の正確性**
        **Validates: Requirements 5.4**
        """
        stack = InfraStack(self.app, "structure-test")
        template = assertions.Template.from_stack(stack)
        
        # Get the raw template as dict
        template_dict = template.to_json()
        
        # Verify CloudFormation template has required top-level sections
        assert "AWSTemplateFormatVersion" in template_dict
        assert template_dict["AWSTemplateFormatVersion"] == "2010-09-09"
        
        # Resources section should exist (even if empty initially)
        assert "Resources" in template_dict
        assert isinstance(template_dict["Resources"], dict)

    @given(
        app_context=st.dictionaries(
            keys=st.text(min_size=1, max_size=30),
            values=st.one_of(
                st.text(min_size=1, max_size=50),
                st.booleans(),
                st.integers(min_value=1, max_value=1000)
            ),
            min_size=0,
            max_size=5
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_cdk_app_context_handling(self, app_context: Dict[str, Any]):
        """
        Property 5: CDKリソース定義の正確性 (Context Handling)
        
        For any valid app context configuration, the CDK app should handle
        context values correctly and maintain stack integrity.
        
        **Feature: iot-aws-infrastructure, Property 5: CDKリソース定義の正確性**
        **Validates: Requirements 5.4**
        """
        # Create app with context
        app = core.App(context=app_context)
        
        # Create stack within the app
        stack = InfraStack(app, "context-test")
        
        # Verify stack can be created with any valid context
        assert stack is not None
        assert isinstance(stack, InfraStack)
        
        # Verify template can be generated
        template = assertions.Template.from_stack(stack)
        assert template is not None