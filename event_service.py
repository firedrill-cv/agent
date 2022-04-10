from logzero import logger
import os
import json
import botocore
import boto3

runner_id = os.environ.get("RUNNER_ID")
eventbridge_client = boto3.client("events")


def send_event(test_suite_run_step_id: str, event_type: str, payload: dict):

    rendered_payload = {}

    if type(payload) is dict:
        rendered_payload = payload
    elif type(payload) is str:
        try:
            rendered_payload = json.loads(payload)
        except:
            logger.error(
                {
                    "method": "send_event",
                    "message": "Attempted to JSON load the payload string but it didn't work.",
                }
            )
            rendered_payload = {"message": payload}
    elif type(payload) is Exception:
        rendered_payload = {"exception": str(payload)}
    else:
        logger.error(
            {
                "message": "Event payload is an unsupported type: {}".format(
                    type(payload)
                )
            }
        )
        rendered_payload = {"exception": "Unsupported payload type."}

    detail = {
        "method": "send_event",
        "event_type": event_type,
        "runner_id": runner_id,
        "test_suite_run_step_id": test_suite_run_step_id,
        "payload": rendered_payload,
    }

    event = {
        "Source": "firedrill.runner",
        "DetailType": event_type,
        "Detail": json.dumps(detail, default=str),
        "EventBusName": "firedrill",
    }
    logger.debug({"message": "Sending event to EventBridge", "event": event})
    try:
        event_result = eventbridge_client.put_events(Entries=[event])

        logger.debug(event_result)

        if event_result["FailedEntryCount"] == 0:
            return {
                "success": True,
            }
        else:
            return {
                "success": False,
                "reason": "FailedEntryCount: {}".format(
                    event_result["FailedEntryCount"]
                ),
            }
    except botocore.exceptions.ParamValidationError as pve:
        logger.error("ParamValidationError")
        print(pve)
        return {"success": False, "reason": "ParamValidationError"}
