import signal
import functions
import queue_monitor
from logzero import logger


class GracefulKiller:
    kill_now = False
    signals = {signal.SIGINT: "SIGINT", signal.SIGTERM: "SIGTERM"}

    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, signum, frame):
        print("\nReceived {} signal".format(self.signals[signum]))
        queue_monitor.stop_watching_queue()
        print("Cleaning up resources. End of the program")
        self.kill_now = True


"""
Detect when a re-delivery is made to the same invocation and ignore it
https://medium.com/appgambit/event-failures-and-retries-with-aws-serverless-messaging-services-a3990fce184d
"""
delivery_ids = []


def run(eventBridgeBody, context):

    if eventBridgeBody["id"] in delivery_ids:
        logger.error(
            {"message": "Duplicate delivery: {}".format(eventBridgeBody["id"])}
        )
        return
    else:
        logger.debug({"message": "New delivery ID: {}".format(eventBridgeBody["id"])})
        delivery_ids.append(eventBridgeBody["id"])

    logger.debug(eventBridgeBody)

    body = eventBridgeBody["detail"]

    # Ensure all of the required fields are provided
    if body == None or "type" not in body:
        raise KeyError("No 'type' parameter in body.")
    elif "payload" not in body:
        raise KeyError("No 'payload' parameter in body.")

    # Start checking the SQS queue for updates
    if "test_suite_run_step_id" in body:
        queue_monitor.start_watching_queue(
            test_suite_run_step_id=body["test_suite_run_step_id"]
        )

    # Healthcheck
    if body["type"] == "healthcheck":
        functions.run_healthcheck()
    # CTK Experiment
    elif body["type"] == "attack.state":
        functions.run_ctk_experiement(body)
    # Resource attack (via SSM, usually)
    elif body["type"] == "attack.resource":
        functions.run_resource_attack(body)
    # Do an inventory scan
    elif body["type"] == "scan.inventory":
        functions.run_service_scan(body)
    # Generic wait step, used for testing
    elif body["type"] == "wait":
        functions.run_wait(body)
    else:
        logger.error(
            {
                "message": "Invalid event type: " + body["type"],
            }
        )

    logger.debug(
        {
            "message": "Finished execution.",
        }
    )
    queue_monitor.stop_watching_queue()
    return
