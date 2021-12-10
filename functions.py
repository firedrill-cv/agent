from datetime import datetime
import time
import mothership
import boto3
import botocore
import json
import os
from chaoslib.experiment import ensure_experiment_is_valid, run_experiment
from chaoslib import __version__ as chaoslib_version
from chaoslib.control import load_global_controls
from chaoslib.discovery import discover as disco
from chaoslib.discovery.discover import portable_type_name_to_python_type
from chaoslib.exceptions import ChaosException, DiscoveryFailed, InvalidSource
from chaoslib.experiment import ensure_experiment_is_valid, run_experiment
from chaoslib.info import list_extensions
from chaoslib.loader import load_experiment
from chaoslib.types import Schedule, Strategy
from chaoslib.notification import (
    DiscoverFlowEvent,
    InitFlowEvent,
    RunFlowEvent,
    ValidateFlowEvent,
    notify,
)
from logzero import logger

# Examples from https://github.com/chaostoolkit/chaostoolkit/blob/master/chaostoolkit/cli.py


service_name_key = 'chaos-service-name'
service_environment_key = 'chaos-service-env'

runner_id = os.environ.get('RUNNER_ID')

# CONSTANT - supported resource types
supported_resource_types = ["dynamodb", "rds", "ecs", "ecr", "ec2",
                            "alb", "elb", "lambda", "eks", "elbv2", "iam", "route53", "ssm"]

eventbridgeClient = boto3.client("events")


def parse_arn_to_components(arn):
    '''
    Parse an AWS arn into it's components
    https://gist.github.com/gene1wood/5299969edc4ef21d8efcfea52158dd40
    '''
    # http://docs.aws.amazon.com/general/latest/gr/aws-arns-and-namespaces.html
    elements = arn.split(':')
    result = {'arn': elements[0],
              'partition': elements[1],
              'resource_type': elements[2],
              'region': elements[3],
              'account': elements[4]
              }
    if len(elements) == 7:
        result['resourcetype'], result['resource'] = elements[5:]
    elif '/' not in elements[5]:
        result['resource'] = elements[5]
        result['resource_sub_type'] = None
    else:
        result['resource_sub_type'], result['resource'] = elements[5].split(
            '/')
    return result


def run_service_scan(execution_id: str, execution_token: str, config: object):
    client = boto3.client('resourcegroupstaggingapi')

    mothership.send_toolkit_event(
        execution_id,
        execution_token,
        "run-started",
        "scan",
        None,
    )

    print("Getting service list, execution ID: " + execution_id)

    done = False
    pagination_token = ''
    services = {}

    # Find the available service names by tag
    while done is False:
        print('Getting tag list: ' + pagination_token)
        response = client.get_tag_values(
            Key=service_name_key,
            PaginationToken=pagination_token
        )
        print(response)

        # Create placeholders for each service we find
        for service in response["TagValues"]:
            print('Found new service: ' + service)
            services[service] = {}

        # Check if we need to go again
        if (response["PaginationToken"] == ''):
            print("Reached end of tags.")
            done = True
        else:
            pagination_token = response["PaginationToken"]
        time.sleep(1)

    # Reset
    done = False
    pagination_token = ''

    print("Getting service resources...")

    # Get each stacks resources
    while done is False:
        print('Getting resource list: ' + pagination_token)
        response = client.get_resources(
            PaginationToken=pagination_token,
            ResourcesPerPage=100,
            TagFilters=[
                {
                    'Key': service_name_key,
                    'Values': list(services.keys())
                },
            ],
        )

        # Append the resources to their respective services
        for resource_mapping in response["ResourceTagMappingList"]:
            # https://stackoverflow.com/a/598407/3018969
            service_name_kv = [
                tag_object for tag_object in resource_mapping["Tags"] if tag_object["Key"] == service_name_key]

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
            print('PARSED:')
            print(parsed_arn)

            resource_details['resource_type'] = parsed_arn['resource_type']
            resource_details['region'] = parsed_arn['region']
            resource_details['account'] = parsed_arn['account']
            resource_details['identifier'] = parsed_arn['resource']
            if 'resource_sub_type' in parsed_arn:
                resource_details['resource_sub_type'] = parsed_arn['resource_sub_type']

            # Environment
            service_env_kv = [
                tag_object for tag_object in resource_mapping["Tags"] if tag_object["Key"] == service_environment_key]
            if service_env_kv == None or service_env_kv[0] == None:
                print("No environment key found for resource: " + resource_arn)
            else:
                print("Environment: {}".format(service_env_kv[0]["Value"]))
                resource_details["environment"] = service_env_kv[0]["Value"]

            # Add this to the final object were building
            print("Found new resource: {}".format(resource_arn))
            services[service_name_kv[0]["Value"]
                     ][resource_arn] = resource_details

        # Check if we need to go again
        if (response["PaginationToken"] == ''):
            print("Reached the end.")
            done = True
        else:
            pagination_token = response["PaginationToken"]
        time.sleep(1)

    print('Found ' + str(len(services)) + ' services in the scan')

    # Send notification mimicing https://chaostoolkit.org/reference/usage/notification/
    mothership.send_toolkit_event(
        execution_id,
        execution_token,
        "run-completed",
        "scan",
        services
    )
    return


def send_event(test_suite_run_step_id: str, event_type: str, payload: dict):

    detail = json.dumps({
        "event_type": event_type,
        "runner_id": runner_id,
        "test_suite_run_step_id": test_suite_run_step_id,
        "payload": payload
    })
    logger.debug({
        "message": "Sending event to EventBridge",
        "detail": detail
    })
    try:
        event_result = eventbridgeClient.put_events(
            Entries=[
                {
                    'Source': 'chinchilla',
                    'DetailType': "Runner Event",
                    'Detail': detail,
                    'EventBusName': "default",
                },
            ]
        )

        if event_result["FailedEntryCount"] == 0:
            return {
                "success": True,
            }
        else:
            return {
                "success": False,
                "reason": "FailedEntryCount: {}".format(event_result["FailedEntryCount"])
            }
    except botocore.exceptions.ParamValidationError as pve:
        logger.error("ParamValidationError")
        print(pve)
        return {
            "success": False,
            "reason": "ParamValidationError"
        }


def run_ctk_experiement(body):
    """
    CTK-based experiment payload
    """
    # Validate
    experiment = body['payload']
    test_suite_run_step_id = body['test_suite_run_step_id']

    logger.debug({
        "message": "Preparing to run experiment",
        "test_suite_run_step_id": test_suite_run_step_id,
        "experiment": experiment,
    })

    try:
        ensure_experiment_is_valid(experiment)
    except ChaosException as x:
        logger.error('Experiment validation failed!')
        logger.error(str(x))
        logger.debug(x)
        return

    logger.debug({
        "method": "run_experiement",
        "message": "Experiment validation succeeded."
    })

    # Generate settings for experiment
    schedule = Schedule(
        1.0, True
    )

    settings = {
        # "notifications": [
        #     {
        #         "type": "http",
        #         "url": body['event_url'],
        #         "headers": {
        #             "x-runner-token": body['runner_token']
        #         }
        #     }
        # ]
    }

    send_event(test_suite_run_step_id, RunFlowEvent.RunStarted.value,
               experiment)

    has_deviated = False
    has_failed = False

    journal = run_experiment(
        experiment,
        settings=settings,
        strategy=Strategy.CONTINUOUS,
        schedule=schedule,
        experiment_vars={},
    )
    journal_status = journal["status"]
    has_deviated = journal.get("deviated", False)
    has_failed = journal["status"] != "completed"

    logger.info({
        "message": "Experiment run completed.",
        "status": journal_status,
        "has_deviated": has_deviated,
        "has_failed": has_failed,
    })

    if journal_status == "completed":
        send_event(test_suite_run_step_id, RunFlowEvent.RunCompleted.value,
                   journal)
    elif has_deviated:
        send_event(test_suite_run_step_id, RunFlowEvent.RunDeviated.value,
                   journal)
    elif has_failed:
        send_event(test_suite_run_step_id, RunFlowEvent.RunFailed.value,
                   journal)

    logger.info({
        "message": "Notifications sent."
    })
    return


def run_step(body: object):
    """
    Run a native chinchilla test suite step
    """
    logger.debug({
        "message": "Running step.",
        "body": str(body),
    })

    return True