from posix import environ
import time
import boto3
from botocore.exceptions import ClientError
import json
import os
from chaoslib.experiment import ensure_experiment_is_valid, run_experiment
from chaoslib import __version__ as chaoslib_version
from chaoslib.control import load_global_controls
from chaoslib.discovery import discover as disco
from chaoslib.discovery.discover import portable_type_name_to_python_type
from chaoslib.exceptions import ChaosException, InvalidSource
from chaoslib.experiment import ensure_experiment_is_valid, run_experiment
from chaoslib.types import Schedule, Strategy
import uuid
from logzero import logger
import sys
import event_service

# Examples from https://github.com/chaostoolkit/chaostoolkit/blob/master/chaostoolkit/cli.py

sqs = boto3.client("sqs")

service_name_key = "chaos-service-name"
service_environment_key = "chaos-service-env"

runner_id = os.environ.get("RUNNER_ID")

# CONSTANT - supported resource types
supported_resource_types = [
    "dynamodb",
    "rds",
    "ecs",
    "ecr",
    "ec2",
    "alb",
    "elb",
    "lambda",
    "eks",
    "elbv2",
    "iam",
    "route53",
    "ssm",
]

ssm_client = boto3.client("ssm")
sqs_client = boto3.client("sqs")
account_id = boto3.client("sts").get_caller_identity().get("Account")
check_interval = 3

message_queue_url = (
    "https://sqs.{}.amazonaws.com/{}/firedrill-runner-messages.fifo".format(
        os.environ.get("AWS_REGION"),
        account_id,
    )
)


def parse_arn_to_components(arn):
    """
    Parse an AWS arn into it's components
    https://gist.github.com/gene1wood/5299969edc4ef21d8efcfea52158dd40
    """
    # http://docs.aws.amazon.com/general/latest/gr/aws-arns-and-namespaces.html
    elements = arn.split(":")
    result = {
        "arn": elements[0],
        "partition": elements[1],
        "resource_type": elements[2],
        "region": elements[3],
        "account": elements[4],
    }
    if len(elements) == 7:
        result["resourcetype"], result["resource"] = elements[5:]
    elif "/" not in elements[5]:
        result["resource"] = elements[5]
        result["resource_sub_type"] = None
    else:
        result["resource_sub_type"], result["resource"] = elements[5].split("/")
    return result


def run_service_scan(execution_id: str, execution_token: str, config: object):
    client = boto3.client("resourcegroupstaggingapi")

    print("Getting service list, execution ID: " + execution_id)

    done = False
    pagination_token = ""
    services = {}

    # Find the available service names by tag
    while done is False:
        print("Getting tag list: " + pagination_token)
        response = client.get_tag_values(
            Key=service_name_key, PaginationToken=pagination_token
        )
        print(response)

        # Create placeholders for each service we find
        for service in response["TagValues"]:
            print("Found new service: " + service)
            services[service] = {}

        # Check if we need to go again
        if response["PaginationToken"] == "":
            print("Reached end of tags.")
            done = True
        else:
            pagination_token = response["PaginationToken"]
        time.sleep(1)

    # Reset
    done = False
    pagination_token = ""

    print("Getting service resources...")

    # Get each stacks resources
    while done is False:
        print("Getting resource list: " + pagination_token)
        response = client.get_resources(
            PaginationToken=pagination_token,
            ResourcesPerPage=100,
            TagFilters=[
                {"Key": service_name_key, "Values": list(services.keys())},
            ],
        )

        # Append the resources to their respective services
        for resource_mapping in response["ResourceTagMappingList"]:
            # https://stackoverflow.com/a/598407/3018969
            service_name_kv = [
                tag_object
                for tag_object in resource_mapping["Tags"]
                if tag_object["Key"] == service_name_key
            ]

            resource_arn = resource_mapping["ResourceARN"]
            resource_details = {
                "arn": resource_arn,
                "environment": None,
                "region": None,
                "account": None,
                "identifier": None,
                "resource_type": None,
                "resource_sub_type": None,
            }

            # Break the ARN into it's components and populate those details
            parsed_arn = parse_arn_to_components(resource_arn)
            print("PARSED:")
            print(parsed_arn)

            resource_details["resource_type"] = parsed_arn["resource_type"]
            resource_details["region"] = parsed_arn["region"]
            resource_details["account"] = parsed_arn["account"]
            resource_details["identifier"] = parsed_arn["resource"]
            if "resource_sub_type" in parsed_arn:
                resource_details["resource_sub_type"] = parsed_arn["resource_sub_type"]

            # Environment
            service_env_kv = [
                tag_object
                for tag_object in resource_mapping["Tags"]
                if tag_object["Key"] == service_environment_key
            ]
            if service_env_kv == None or service_env_kv[0] == None:
                print("No environment key found for resource: " + resource_arn)
            else:
                print("Environment: {}".format(service_env_kv[0]["Value"]))
                resource_details["environment"] = service_env_kv[0]["Value"]

            # Add this to the final object were building
            print("Found new resource: {}".format(resource_arn))
            services[service_name_kv[0]["Value"]][resource_arn] = resource_details

        # Check if we need to go again
        if response["PaginationToken"] == "":
            print("Reached the end.")
            done = True
        else:
            pagination_token = response["PaginationToken"]
        time.sleep(1)

    print("Found " + str(len(services)) + " services in the scan")

    return


def run_ctk_experiement(body):
    """
    CTK-based experiment payload
    """
    # Validate
    if "payload" not in body:
        raise KeyError("Failed to run - no 'payload' parameter in body.")

    experiment = body["payload"]
    test_suite_run_step_id = body["test_suite_run_step_id"]
    is_rollback = body["is_rollback"]

    logger.debug(
        {
            "message": "Preparing to run Chaos Toolkit experiment",
            "test_suite_run_step_id": test_suite_run_step_id,
        }
    )

    try:
        ensure_experiment_is_valid(experiment)
    except ChaosException as x:
        logger.error("Experiment validation failed!")
        logger.error(str(x))
        logger.debug(x)
        return

    logger.debug(
        {"method": "run_experiement", "message": "Experiment validation succeeded."}
    )

    # Generate settings for experiment
    schedule = Schedule(1.0, True)

    event_service.send_event(
        test_suite_run_step_id=test_suite_run_step_id,
        event_type="started",
        payload={},
        is_rollback=is_rollback,
    )

    has_deviated = False
    has_failed = False

    journal = run_experiment(
        experiment,
        schedule=schedule,
        experiment_vars={},
    )
    journal_status = journal["status"]
    has_deviated = journal.get("deviated", False)
    has_failed = journal["status"] != "completed"

    logger.info(
        {
            "message": "Experiment run completed.",
            "status": journal_status,
            "has_deviated": has_deviated,
            "has_failed": has_failed,
        }
    )

    event_payload = {
        "has_deviated": has_deviated,
        "has_failed": has_failed,
        "status": journal_status,
    }
    if journal_status == "completed":
        event_service.send_event(
            test_suite_run_step_id=test_suite_run_step_id,
            event_type="completed",
            payload=event_payload,
            is_rollback=is_rollback,
        )
    elif has_deviated:
        event_service.send_event(
            test_suite_run_step_id=test_suite_run_step_id,
            event_type="deviated",
            payload=event_payload,
            is_rollback=is_rollback,
        )
    elif has_failed:
        event_service.send_event(
            test_suite_run_step_id=test_suite_run_step_id,
            event_type="failed",
            payload=event_payload,
            is_rollback=is_rollback,
        )

    logger.info({"message": "Notifications sent."})
    return


def run_resource_attack(body: object):
    """
    Only runs SSM-based attacks right now
    """
    if "payload" not in body:
        raise KeyError("Failed to run - no 'payload' parameter in body.")

    ssm_document = body["payload"]
    test_suite_run_step_id = body["test_suite_run_step_id"]
    is_rollback = body["is_rollback"]

    logger.debug(
        {
            "message": "Running SSM based attack.",
            "test_suite_run_step_id": test_suite_run_step_id,
            "ssm_document": str(ssm_document),
        }
    )

    try:
        response = ssm_client.send_command(**ssm_document)
        command_id = response["Command"]["CommandId"]
        pending_instance_ids = response["Command"]["InstanceIds"]
        status_code = response["ResponseMetadata"]["HTTPStatusCode"]
        request_id = response["ResponseMetadata"]["RequestId"]

        if status_code != 200:
            logger.error(
                {
                    "message": "Non-200 HTTP code returned from SSM",
                    "test_suite_run_step_id": test_suite_run_step_id,
                    "status_code": status_code,
                    "command_id": command_id,
                    "request_id": request_id,
                }
            )
            return False

        logger.debug(
            {
                "message": "Sent command successfully, waiting for command completion on all instances",
                "test_suite_run_step_id": test_suite_run_step_id,
                "request_id": request_id,
                "response": response,
                "command_id": command_id,
                "instance_ids": pending_instance_ids,
            }
        )

        # Send command ID
        event_service.send_event(
            test_suite_run_step_id=test_suite_run_step_id,
            event_type="started",
            payload={
                "command_id": command_id,
                "instance_ids": pending_instance_ids,
                "ssm_document": str(ssm_document),
            },
            is_rollback=is_rollback,
        )

        # Watch the command for the provided timeout
        while len(pending_instance_ids) > 0:

            # Check if we should continue
            should_continue = check_messages_queue(test_suite_run_step_id)

            # If a killswitch was received, cancel running SSM commands
            if should_continue == False:
                try:
                    stop_command_result = ssm_client.cancel_command(
                        CommandId=command_id,
                        InstanceIds=pending_instance_ids,
                    )
                    event_service.send_event(
                        test_suite_run_step_id=test_suite_run_step_id,
                        event_type="stopped",
                        payload={
                            "stop_command_result": stop_command_result,
                            "ssm_document": str(ssm_document),
                        },
                        is_rollback=is_rollback,
                    )
                    logger.info(
                        {
                            "message": "Successfully stopped running SSM commands.",
                            "command_id": command_id,
                            "instance_ids": pending_instance_ids,
                        }
                    )
                    sys.exit(0)

                except Exception as ex:
                    logger.error(
                        {
                            "message": "Failed to stop running SSM commands",
                            "ex": str(ex),
                        }
                    )
                    return

            # Iterate through the execution statuses and see what their status is
            for instance_id in pending_instance_ids:
                try:
                    response = ssm_client.get_command_invocation(
                        CommandId=command_id,
                        InstanceId=instance_id,
                    )
                except Exception as ex:
                    logger.error(
                        {
                            "message": "Failed to check status of SSM command",
                            "instance_id": instance_id,
                            "instance_status": command_id,
                            "error": str(ex),
                        }
                    )
                    continue

                # Process the status: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ssm.html#SSM.Client.get_command_invocation
                instance_status = response["Status"]
                logger.debug(
                    {
                        "message": "Waiting for instance command to finish running...",
                        "instance_id": instance_id,
                        "instance_status": instance_status,
                    }
                )

                # If we're still waiting for it
                if instance_status == "Pending" or instance_status == "InProgress":
                    continue

                # If it's successfully completed, remove it from the list
                elif instance_status == "Success":
                    logger.debug(
                        {
                            "message": "Execution finished on instance.",
                            "instance_id": instance_id,
                            "instance_status": instance_status,
                        }
                    )
                    pending_instance_ids.remove(instance_id)
                    continue

                # If it's any other status, don't proceed and stop this runner
                else:
                    logger.error(
                        {
                            "message": "Instance returned invalid status, will stop watching it. Dumping full response below for debugging.",
                            "instance_id": instance_id,
                            "instance_status": instance_status,
                        }
                    )
                    logger.debug(response)
                    event_service.send_event(
                        test_suite_run_step_id=test_suite_run_step_id,
                        event_type="failed",
                        is_rollback=is_rollback,
                        payload={
                            "command_id": command_id,
                            "message": "Instance returned invalid status, will stop watching it.",
                            "target_instance_id": instance_id,
                            "status": instance_status,
                        },
                    )
                    return

        logger.debug({"message": "Successfully ran SSM commands on instances"})
        event_service.send_event(
            test_suite_run_step_id=test_suite_run_step_id,
            event_type="completed",
            is_rollback=is_rollback,
            payload={
                "message": "Command finished on all targeted instances.",
                "command_id": command_id,
                "ssm_document": str(ssm_document),
            },
        )
    except ClientError as cer:

        try:
            payload = json.dumps(cer)
        except Exception as ex:
            payload = str(cer)

        logger.error(
            {
                "message": "ClientError thrown when sending SSM attack",
                "ssm_document": str(ssm_document),
                "exception": payload,
            }
        )

        event_service.send_event(
            test_suite_run_step_id=test_suite_run_step_id,
            event_type="failed",
            payload=payload,
            is_rollback=is_rollback,
        )

        return False

    except Exception as ex:
        logger.error(ex)

        try:
            payload = json.dumps(ex)
        except Exception as ex:
            payload = str(ex)

        event_service.send_event(
            test_suite_run_step_id=test_suite_run_step_id,
            event_type="failed",
            payload=payload,
            is_rollback=is_rollback,
        )
        return False


def run_wait(body: object):
    test_suite_run_step_id = body["test_suite_run_step_id"]
    is_rollback = body["is_rollback"]

    timeToSleep = 30
    if "time" in body["payload"]:
        timeToSleep = int(body["payload"]["time"])

    logger.info(
        {
            "message": "Waiting for {} seconds.".format(timeToSleep),
            "test_suite_run_step_id": test_suite_run_step_id,
        }
    )

    event_service.send_event(
        test_suite_run_step_id=test_suite_run_step_id,
        event_type="started",
        payload={},
        is_rollback=is_rollback,
    )
    time.sleep(timeToSleep)
    logger.info(
        {
            "message": "Wait complete.",
            "test_suite_run_step_id": test_suite_run_step_id,
        }
    )
    event_service.send_event(
        test_suite_run_step_id=test_suite_run_step_id,
        event_type="completed",
        payload={},
        is_rollback=is_rollback,
    )
    return True


def run_healthcheck():
    logger.info(
        {
            "message": "Healthcheck initiated",
        }
    )
    event_service.send_event(
        test_suite_run_step_id="healthcheck",
        event_type="healthcheck",
        is_rollback=False,
        payload={
            "is_default": True,
            "AWS_REGION": os.environ.get("AWS_REGION"),
            "AWS_ACCESS_KEY_ID": os.environ.get("AWS_ACCESS_KEY_ID"),
            "AWS_LAMBDA_FUNCTION_NAME": os.environ.get("AWS_LAMBDA_FUNCTION_NAME"),
        },
    )


def check_messages_queue(test_suite_run_step_id) -> bool:
    """
    Checks incoming queue for messages and returns a Boolean
    If False, the execution should stop
    """

    response = sqs.receive_message(
        QueueUrl=message_queue_url,
        AttributeNames=["All"],
        MaxNumberOfMessages=10,
        WaitTimeSeconds=check_interval,
    )

    if "Messages" not in response or len(response["Messages"]) == 0:
        logger.debug(
            {
                "test_suite_run_step_id": test_suite_run_step_id,
                "message": "No messages in queue.",
            }
        )
        return

    messages = response["Messages"]

    should_continue = True

    for message in messages:
        if "Body" not in message:
            logger.error(
                {
                    "test_suite_run_step_id": test_suite_run_step_id,
                    "message": "No Body in message, ignoring.",
                }
            )
            return

        message_body = message["Body"].strip()
        try:
            message_body = json.loads(message_body)
            logger.debug(
                {
                    "message": "Received message and decoded successfully",
                    "message_body": message_body,
                }
            )
        except Exception as ex:
            logger.error(
                {
                    "message": "Failed to JSON load the message body, not continuing",
                    "message_body": message_body,
                    "error": str(ex),
                }
            )
            return

        message_type = message_body["type"]
        target_test_suite_run_step_id = message_body["id"]

        if test_suite_run_step_id != target_test_suite_run_step_id:
            logger.debug(
                {
                    "message": "Message found but wasn't intended for this step.",
                    "target_test_suite_run_step_id": target_test_suite_run_step_id,
                    "test_suite_run_step_id": test_suite_run_step_id,
                }
            )
            continue

        sqs.delete_message(
            QueueUrl=message_queue_url, ReceiptHandle=message["ReceiptHandle"]
        )

        logger.debug(
            {
                "test_suite_run_step_id": test_suite_run_step_id,
                "message": "Received message for this runner.",
                "message_type": message_type,
            }
        )

        if message_type == "killswitch":
            logger.debug(
                {
                    "test_suite_run_step_id": test_suite_run_step_id,
                    "message": "KILLSWITCH RECEIVED! Stopping execution.",
                }
            )
            should_continue = False

    return should_continue


def proxy_message(body: object):
    """
    Takes messages from the main inbound queue and puts them  in the local FIFO queue so
    runners in progress can read them
    """
    message = {
        "type": body["message_type"],
        "target": "runner",
        "id": body["test_suite_run_step_id"],
    }

    try:
        sqs_client.send_message(
            QueueUrl=message_queue_url,
            MessageGroupId="inbound-runner-messages",
            MessageDeduplicationId=str(uuid.uuid4()),
            MessageBody=json.dumps(message),
        )

        logger.debug(
            {
                "message": "Put proxymessage in FIFO queue successfully",
                "body": message,
            }
        )
    except Exception as ex:
        logger.error(
            {"message": "Failed to put message in FIFO queue.", "error": str(ex)}
        )
