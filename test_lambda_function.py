import json
import os
import pytest
from unittest.mock import patch, MagicMock

# Import the lambda function module
import lambda_function


@pytest.fixture
def env_vars():
    """Set up environment variables for testing."""
    os.environ["HOSTED_ZONE_ID"] = "Z1234567890ABC"
    os.environ["RECORD_SET_NAME"] = "example.com."
    os.environ["PRIMARY_IDENTIFIER"] = "primary"
    os.environ["SECONDARY_IDENTIFIER"] = "secondary"
    os.environ["RECORD_TYPE"] = "A"
    yield
    # Cleanup
    for key in [
        "HOSTED_ZONE_ID",
        "RECORD_SET_NAME",
        "PRIMARY_IDENTIFIER",
        "SECONDARY_IDENTIFIER",
        "RECORD_TYPE",
    ]:
        os.environ.pop(key, None)


@pytest.fixture
def alarm_event():
    """Create a sample CloudWatch alarm event via SNS."""
    return {
        "Records": [
            {
                "Sns": {
                    "Message": json.dumps(
                        {
                            "AlarmName": "test-alarm",
                            "NewStateValue": "ALARM",
                            "NewStateReason": "Threshold Crossed",
                        }
                    )
                }
            }
        ]
    }


@pytest.fixture
def ok_event():
    """Create a sample CloudWatch OK event via SNS."""
    return {
        "Records": [
            {
                "Sns": {
                    "Message": json.dumps(
                        {
                            "AlarmName": "test-alarm",
                            "NewStateValue": "OK",
                            "NewStateReason": "Threshold Normal",
                        }
                    )
                }
            }
        ]
    }


class TestValidateEnvironmentVariables:
    """Test environment variable validation."""

    def test_all_variables_present(self, env_vars):
        """Test validation when all required variables are present."""
        result = lambda_function.validate_environment_variables()
        assert result["HOSTED_ZONE_ID"] == "Z1234567890ABC"
        assert result["RECORD_SET_NAME"] == "example.com."
        assert result["PRIMARY_IDENTIFIER"] == "primary"
        assert result["SECONDARY_IDENTIFIER"] == "secondary"
        assert result["RECORD_TYPE"] == "A"

    def test_missing_variable(self):
        """Test validation when a required variable is missing."""
        os.environ["HOSTED_ZONE_ID"] = "Z123"
        with pytest.raises(ValueError, match="Missing required environment variables"):
            lambda_function.validate_environment_variables()

    def test_adds_trailing_dot(self):
        """Test that trailing dot is added to RECORD_SET_NAME if missing."""
        os.environ["HOSTED_ZONE_ID"] = "Z123"
        os.environ["RECORD_SET_NAME"] = "example.com"
        os.environ["PRIMARY_IDENTIFIER"] = "primary"
        os.environ["SECONDARY_IDENTIFIER"] = "secondary"
        os.environ["RECORD_TYPE"] = "A"

        result = lambda_function.validate_environment_variables()
        assert result["RECORD_SET_NAME"] == "example.com."


class TestValidateSnsMessage:
    """Test SNS message validation."""

    def test_valid_alarm_message(self, alarm_event):
        """Test validation of valid ALARM message."""
        result = lambda_function.validate_sns_message(alarm_event)
        assert result == "ALARM"

    def test_valid_ok_message(self, ok_event):
        """Test validation of valid OK message."""
        result = lambda_function.validate_sns_message(ok_event)
        assert result == "OK"

    def test_missing_records_field(self):
        """Test validation with missing Records field."""
        event = {}
        result = lambda_function.validate_sns_message(event)
        assert result is None

    def test_empty_records(self):
        """Test validation with empty Records array."""
        event = {"Records": []}
        result = lambda_function.validate_sns_message(event)
        assert result is None

    def test_missing_sns_field(self):
        """Test validation with missing Sns field."""
        event = {"Records": [{}]}
        result = lambda_function.validate_sns_message(event)
        assert result is None

    def test_missing_message_field(self):
        """Test validation with missing Message field."""
        event = {"Records": [{"Sns": {}}]}
        result = lambda_function.validate_sns_message(event)
        assert result is None

    def test_invalid_json_in_message(self):
        """Test validation with invalid JSON in Message field."""
        event = {"Records": [{"Sns": {"Message": "not-json"}}]}
        result = lambda_function.validate_sns_message(event)
        assert result is None

    def test_missing_new_state_value(self):
        """Test validation with missing NewStateValue."""
        event = {"Records": [{"Sns": {"Message": json.dumps({"AlarmName": "test"})}}]}
        result = lambda_function.validate_sns_message(event)
        assert result is None

    def test_insufficient_data_state(self):
        """Test validation with INSUFFICIENT_DATA state."""
        event = {
            "Records": [
                {"Sns": {"Message": json.dumps({"NewStateValue": "INSUFFICIENT_DATA"})}}
            ]
        }
        result = lambda_function.validate_sns_message(event)
        assert result == "INSUFFICIENT_DATA"


class TestGetAliasTargetDnsName:
    """Test alias target DNS name retrieval."""

    @patch("lambda_function.route53_client")
    def test_successful_retrieval(self, mock_client):
        """Test successful retrieval of alias target."""
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "ResourceRecordSets": [
                    {
                        "Name": "example.com.",
                        "Type": "A",
                        "SetIdentifier": "primary",
                        "AliasTarget": {
                            "DNSName": "alias.example.com.",
                            "HostedZoneId": "Z987654321",
                        },
                    }
                ]
            }
        ]

        result = lambda_function.get_alias_target_dns_name(
            "Z123", "example.com.", "primary", "A"
        )

        assert result == ("alias.example.com.", "Z987654321")

    @patch("lambda_function.route53_client")
    def test_record_not_found(self, mock_client):
        """Test when record is not found."""
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{"ResourceRecordSets": []}]

        result = lambda_function.get_alias_target_dns_name(
            "Z123", "example.com.", "primary", "A"
        )

        assert result is None

    @patch("lambda_function.route53_client")
    def test_no_alias_target(self, mock_client):
        """Test when record exists but has no AliasTarget."""
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "ResourceRecordSets": [
                    {
                        "Name": "example.com.",
                        "Type": "A",
                        "SetIdentifier": "primary",
                        "ResourceRecords": [{"Value": "1.2.3.4"}],
                    }
                ]
            }
        ]

        result = lambda_function.get_alias_target_dns_name(
            "Z123", "example.com.", "primary", "A"
        )

        assert result is None

    @patch("lambda_function.route53_client")
    def test_pagination(self, mock_client):
        """Test that pagination works correctly."""
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {"ResourceRecordSets": [{"Name": "aaa.com.", "Type": "A"}]},
            {
                "ResourceRecordSets": [
                    {
                        "Name": "example.com.",
                        "Type": "A",
                        "SetIdentifier": "primary",
                        "AliasTarget": {
                            "DNSName": "alias.example.com.",
                            "HostedZoneId": "Z987654321",
                        },
                    }
                ]
            },
        ]

        result = lambda_function.get_alias_target_dns_name(
            "Z123", "example.com.", "primary", "A"
        )

        assert result == ("alias.example.com.", "Z987654321")

    @patch("lambda_function.route53_client")
    def test_api_error(self, mock_client):
        """Test handling of API errors."""
        mock_client.get_paginator.side_effect = Exception("API Error")

        result = lambda_function.get_alias_target_dns_name(
            "Z123", "example.com.", "primary", "A"
        )

        assert result is None


class TestSetDnsRecordWeight:
    """Test DNS record weight updates."""

    @patch("lambda_function.route53_client")
    def test_successful_weight_update(self, mock_client):
        """Test successful weight update."""
        mock_client.change_resource_record_sets.return_value = {
            "ChangeInfo": {"Id": "change-123", "Status": "PENDING"}
        }

        result = lambda_function.set_dns_record_weight(
            "Z123", "example.com.", "A", "primary", 1, "alias.example.com.", "Z987"
        )

        assert result is True
        mock_client.change_resource_record_sets.assert_called_once()

    @patch("lambda_function.route53_client")
    def test_api_error(self, mock_client):
        """Test handling of API errors during weight update."""
        mock_client.change_resource_record_sets.side_effect = Exception("API Error")

        result = lambda_function.set_dns_record_weight(
            "Z123", "example.com.", "A", "primary", 1, "alias.example.com.", "Z987"
        )

        assert result is False


class TestLambdaHandler:
    """Test the main Lambda handler function."""

    @patch("lambda_function.set_dns_record_weight")
    @patch("lambda_function.get_alias_target_dns_name")
    def test_alarm_state_switches_to_secondary(
        self, mock_get_alias, mock_set_weight, env_vars, alarm_event
    ):
        """Test that ALARM state switches traffic to secondary."""
        mock_get_alias.side_effect = [
            ("primary.example.com.", "Z111"),
            ("secondary.example.com.", "Z222"),
        ]
        mock_set_weight.return_value = True

        response = lambda_function.lambda_handler(alarm_event, None)

        assert response["statusCode"] == 200
        assert "successfully" in response["body"]

        # Check that weights were set correctly
        calls = mock_set_weight.call_args_list
        # Primary should be set to 0
        assert calls[0][0][4] == 0  # weight for primary
        # Secondary should be set to 1
        assert calls[1][0][4] == 1  # weight for secondary

    @patch("lambda_function.set_dns_record_weight")
    @patch("lambda_function.get_alias_target_dns_name")
    def test_ok_state_switches_to_primary(
        self, mock_get_alias, mock_set_weight, env_vars, ok_event
    ):
        """Test that OK state switches traffic to primary."""
        mock_get_alias.side_effect = [
            ("primary.example.com.", "Z111"),
            ("secondary.example.com.", "Z222"),
        ]
        mock_set_weight.return_value = True

        response = lambda_function.lambda_handler(ok_event, None)

        assert response["statusCode"] == 200
        assert "successfully" in response["body"]

        # Check that weights were set correctly
        calls = mock_set_weight.call_args_list
        # Primary should be set to 1
        assert calls[0][0][4] == 1  # weight for primary
        # Secondary should be set to 0
        assert calls[1][0][4] == 0  # weight for secondary

    @patch("lambda_function.get_alias_target_dns_name")
    def test_missing_env_variable(self, mock_get_alias, alarm_event):
        """Test error handling when environment variable is missing."""
        response = lambda_function.lambda_handler(alarm_event, None)

        assert response["statusCode"] == 500
        assert "Configuration error" in response["body"]

    @patch("lambda_function.get_alias_target_dns_name")
    def test_invalid_event_structure(self, mock_get_alias, env_vars):
        """Test error handling for invalid event structure."""
        invalid_event = {"invalid": "structure"}

        response = lambda_function.lambda_handler(invalid_event, None)

        assert response["statusCode"] == 400
        assert "Invalid event structure" in response["body"]

    @patch("lambda_function.get_alias_target_dns_name")
    def test_alias_lookup_failure(self, mock_get_alias, env_vars, alarm_event):
        """Test error handling when alias lookup fails."""
        mock_get_alias.return_value = None

        response = lambda_function.lambda_handler(alarm_event, None)

        assert response["statusCode"] == 500
        assert "Failed to retrieve alias DNS information" in response["body"]

    @patch("lambda_function.set_dns_record_weight")
    @patch("lambda_function.get_alias_target_dns_name")
    def test_weight_update_failure(
        self, mock_get_alias, mock_set_weight, env_vars, alarm_event
    ):
        """Test error handling when weight update fails."""
        mock_get_alias.side_effect = [
            ("primary.example.com.", "Z111"),
            ("secondary.example.com.", "Z222"),
        ]
        mock_set_weight.return_value = False

        response = lambda_function.lambda_handler(alarm_event, None)

        assert response["statusCode"] == 500
        assert "Failed to update DNS weights" in response["body"]

    @patch("lambda_function.get_alias_target_dns_name")
    def test_insufficient_data_state(self, mock_get_alias, env_vars):
        """Test handling of INSUFFICIENT_DATA state."""
        event = {
            "Records": [
                {"Sns": {"Message": json.dumps({"NewStateValue": "INSUFFICIENT_DATA"})}}
            ]
        }
        mock_get_alias.side_effect = [
            ("primary.example.com.", "Z111"),
            ("secondary.example.com.", "Z222"),
        ]

        response = lambda_function.lambda_handler(event, None)

        assert response["statusCode"] == 200
        assert "No action taken" in response["body"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
