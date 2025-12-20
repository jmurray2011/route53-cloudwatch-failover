import logging
import boto3
import json
import os
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

# Setup logging for Lambda
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Initialize AWS clients
route53_client = boto3.client("route53")


@dataclass
class RecordInfo:
    """Information about a DNS record for weight updates."""

    is_alias: bool
    # For ALIAS records
    alias_dns_name: Optional[str] = None
    alias_hosted_zone_id: Optional[str] = None
    # For standard records (A, AAAA, CNAME)
    resource_records: Optional[List[str]] = None
    ttl: Optional[int] = None


def validate_environment_variables() -> Dict[str, str]:
    """
    Validate and retrieve required environment variables.

    Returns:
        Dictionary containing all required environment variables.

    Raises:
        ValueError: If any required environment variable is missing.
    """
    required_vars = [
        "HOSTED_ZONE_ID",
        "RECORD_SET_NAME",
        "PRIMARY_IDENTIFIER",
        "SECONDARY_IDENTIFIER",
        "RECORD_TYPE",
    ]

    env_vars = {}
    missing_vars = []

    for var in required_vars:
        value = os.environ.get(var)
        if not value:
            missing_vars.append(var)
        else:
            env_vars[var] = value

    if missing_vars:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing_vars)}"
        )

    # Validate RECORD_SET_NAME has trailing dot
    if not env_vars["RECORD_SET_NAME"].endswith("."):
        logger.warning(
            f"RECORD_SET_NAME '{env_vars['RECORD_SET_NAME']}' does not end with a dot. Adding it."
        )
        env_vars["RECORD_SET_NAME"] += "."

    return env_vars


def get_record_info(
    hosted_zone_id: str, record_set_name: str, identifier: str, record_type: str
) -> Optional[RecordInfo]:
    """
    Retrieve information about a DNS record for weight updates.

    Supports both ALIAS records and standard records (A, AAAA, CNAME).

    Args:
        hosted_zone_id: The ID of the hosted zone that contains the DNS records.
        record_set_name: The name of the DNS record set to retrieve.
        identifier: The set identifier for the weighted routing record.
        record_type: The type of the DNS record set to retrieve.

    Returns:
        RecordInfo object if found, None otherwise.
    """
    try:
        # Use paginator to handle large record sets
        paginator = route53_client.get_paginator("list_resource_record_sets")
        page_iterator = paginator.paginate(  # type: ignore[call-arg]
            HostedZoneId=hosted_zone_id,
            StartRecordName=record_set_name,
            StartRecordType=record_type,
        )

        # Search through pages for the matching record
        for page in page_iterator:
            for record_set in page["ResourceRecordSets"]:
                # Stop if we've moved past our target record name
                if record_set["Name"] > record_set_name:
                    break

                if (
                    record_set["Name"] == record_set_name
                    and record_set.get("SetIdentifier") == identifier
                    and record_set["Type"] == record_type
                ):
                    # Check if it's an ALIAS record
                    if "AliasTarget" in record_set:
                        alias_target = record_set["AliasTarget"]
                        return RecordInfo(
                            is_alias=True,
                            alias_dns_name=alias_target["DNSName"],
                            alias_hosted_zone_id=alias_target["HostedZoneId"],
                        )
                    # Standard record (A, AAAA, CNAME, etc.)
                    elif "ResourceRecords" in record_set:
                        return RecordInfo(
                            is_alias=False,
                            resource_records=[
                                rr["Value"] for rr in record_set["ResourceRecords"]
                            ],
                            ttl=record_set.get("TTL", 300),
                        )

        logger.error(
            f"Record not found for {record_set_name} with identifier '{identifier}' "
            f"and type {record_type}."
        )
        return None

    except Exception as e:
        logger.error(f"Error retrieving record info: {e}", exc_info=True)
        return None


def set_dns_record_weight(
    hosted_zone_id: str,
    record_set_name: str,
    record_type: str,
    identifier: str,
    weight: int,
    record_info: RecordInfo,
) -> bool:
    """
    Set the weight of a DNS record set.

    Supports both ALIAS records and standard records (A, AAAA, CNAME).

    Args:
        hosted_zone_id: The ID of the hosted zone.
        record_set_name: The name of the DNS record set.
        record_type: The type of DNS record.
        identifier: A string identifying the DNS record set.
        weight: The new weight for the DNS record.
        record_info: RecordInfo object containing record details.

    Returns:
        True if successful, False otherwise.
    """
    try:
        # Build the base record set
        resource_record_set: Dict[str, Any] = {
            "Name": record_set_name,
            "Type": record_type,
            "Weight": weight,
            "SetIdentifier": identifier,
        }

        # Add type-specific fields
        if record_info.is_alias:
            resource_record_set["AliasTarget"] = {
                "DNSName": record_info.alias_dns_name,
                "HostedZoneId": record_info.alias_hosted_zone_id,
                "EvaluateTargetHealth": False,
            }
        else:
            resource_record_set["TTL"] = record_info.ttl or 300
            resource_record_set["ResourceRecords"] = [
                {"Value": value} for value in (record_info.resource_records or [])
            ]

        change_batch = {
            "Changes": [{"Action": "UPSERT", "ResourceRecordSet": resource_record_set}]
        }

        # Update the DNS record set
        response = route53_client.change_resource_record_sets(
            HostedZoneId=hosted_zone_id, ChangeBatch=change_batch  # type: ignore[arg-type]
        )
        logger.info(
            f"DNS record {record_set_name} - {identifier} weight updated to {weight}. "
            f"Change ID: {response['ChangeInfo']['Id']}"
        )
        return True

    except Exception as e:
        logger.error(f"Error setting DNS record weight: {e}", exc_info=True)
        return False


def validate_sns_message(event: Dict[str, Any]) -> Optional[str]:
    """
    Validate and extract the alarm state from SNS event.

    Args:
        event: The Lambda event dictionary.

    Returns:
        The new state value ('ALARM' or 'OK') if valid, None otherwise.
    """
    try:
        # Validate event structure
        if "Records" not in event:
            logger.error("Event missing 'Records' field")
            return None

        if not event["Records"] or len(event["Records"]) == 0:
            logger.error("Event 'Records' is empty")
            return None

        # Extract SNS message
        sns_record = event["Records"][0]
        if "Sns" not in sns_record:
            logger.error("Record missing 'Sns' field")
            return None

        sns_message_str = sns_record["Sns"].get("Message")
        if not sns_message_str:
            logger.error("SNS record missing 'Message' field")
            return None

        # Parse SNS message
        sns_message = json.loads(sns_message_str)

        # Extract and validate new state
        new_state = sns_message.get("NewStateValue")
        if not new_state:
            logger.error("SNS message missing 'NewStateValue' field")
            return None

        if new_state not in ["ALARM", "OK", "INSUFFICIENT_DATA"]:
            logger.warning(f"Unexpected alarm state: {new_state}")
            return None

        return new_state

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse SNS message as JSON: {e}", exc_info=True)
        return None
    except (KeyError, IndexError) as e:
        logger.error(f"Error extracting data from event: {e}", exc_info=True)
        return None


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler function triggered by a CloudWatch alarm via SNS.

    Args:
        event: The event dict that contains the SNS message with CloudWatch Alarm state change.
        context: The Lambda context runtime information.

    Returns:
        Dictionary with statusCode and body indicating success or failure.
    """
    logger.info(f"Received event: {json.dumps(event)}")

    try:
        # Validate environment variables
        env_vars = validate_environment_variables()
        hosted_zone_id = env_vars["HOSTED_ZONE_ID"]
        record_set_name = env_vars["RECORD_SET_NAME"]
        primary_identifier = env_vars["PRIMARY_IDENTIFIER"]
        secondary_identifier = env_vars["SECONDARY_IDENTIFIER"]
        record_type = env_vars["RECORD_TYPE"]

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Configuration error", "message": str(e)}),
        }

    # Validate and extract SNS message
    new_state = validate_sns_message(event)
    if not new_state:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Invalid event structure"}),
        }

    logger.info(f"Processing alarm state: {new_state}")

    # Retrieve record information for both primary and secondary
    pri_record_info = get_record_info(
        hosted_zone_id, record_set_name, primary_identifier, record_type
    )
    sec_record_info = get_record_info(
        hosted_zone_id, record_set_name, secondary_identifier, record_type
    )

    # Check if both records were found
    if not pri_record_info or not sec_record_info:
        error_msg = "Failed to retrieve record information for "
        if not pri_record_info:
            error_msg += f"primary identifier '{primary_identifier}'"
        if not sec_record_info:
            separator = " and " if not pri_record_info else ""
            error_msg += f"{separator}secondary identifier '{secondary_identifier}'"

        logger.error(error_msg)
        return {"statusCode": 500, "body": json.dumps({"error": error_msg})}

    # Update weights based on alarm state
    success = True
    if new_state == "ALARM":
        logger.info("ALARM state detected - routing traffic to secondary")
        success = set_dns_record_weight(
            hosted_zone_id,
            record_set_name,
            record_type,
            primary_identifier,
            0,
            pri_record_info,
        ) and set_dns_record_weight(
            hosted_zone_id,
            record_set_name,
            record_type,
            secondary_identifier,
            1,
            sec_record_info,
        )
    elif new_state == "OK":
        logger.info("OK state detected - routing traffic to primary")
        success = set_dns_record_weight(
            hosted_zone_id,
            record_set_name,
            record_type,
            primary_identifier,
            1,
            pri_record_info,
        ) and set_dns_record_weight(
            hosted_zone_id,
            record_set_name,
            record_type,
            secondary_identifier,
            0,
            sec_record_info,
        )
    else:
        logger.warning(f"Unhandled alarm state: {new_state} - no action taken")
        return {
            "statusCode": 200,
            "body": json.dumps({"message": f"No action taken for state: {new_state}"}),
        }

    if success:
        logger.info("DNS weights updated successfully")
        return {
            "statusCode": 200,
            "body": json.dumps(
                {"message": f"DNS weights updated successfully for state: {new_state}"}
            ),
        }
    else:
        logger.error("Failed to update DNS weights")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Failed to update DNS weights"}),
        }


if __name__ == "__main__":
    # Example event payload for testing
    test_event = {
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

    # Set test environment variables
    os.environ["HOSTED_ZONE_ID"] = "Z1234567890ABC"
    os.environ["RECORD_SET_NAME"] = "example.com."
    os.environ["PRIMARY_IDENTIFIER"] = "primary"
    os.environ["SECONDARY_IDENTIFIER"] = "secondary"
    os.environ["RECORD_TYPE"] = "A"

    result = lambda_handler(test_event, None)
    print(f"Test result: {json.dumps(result, indent=2)}")
