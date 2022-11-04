import signal
import functions
from logzero import logger


class GracefulKiller:
    kill_now = False
    signals = {signal.SIGINT: "SIGINT", signal.SIGTERM: "SIGTERM"}

    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, signum, frame):
        print("\nReceived {} signal".format(self.signals[signum]))
        self.kill_now = True


"""
Detect when a re-delivery is made to the same invocation and ignore it
https://medium.com/appgambit/event-failures-and-retries-with-aws-serverless-messaging-services-a3990fce184d
"""
delivery_ids = []


def run(eventBridgeBody, context):

    if eventBridgeBody["id"] in delivery_ids:
        logger.error(
            {
                "message": "Duplicate delivery, not processing",
                "id": eventBridgeBody["id"],
            }
        )
        return
    else:
        delivery_ids.append(eventBridgeBody["id"])

    logger.debug(eventBridgeBody)

    body = eventBridgeBody["detail"]

    # Ensure all of the required fields are provided
    if body == None or "type" not in body:
        logger.error(
            {
                "message": "No 'type' parameter in body.",
                "eventbridge_id": eventBridgeBody["id"],
            }
        )
        return False

    # Healthcheck
    if body["type"] == "healthcheck":
        functions.run_healthcheck()
    # Messages for runners in progress - get added to local FIFO queue
    if body["type"] == "message":
        functions.proxy_message(body)
    # CTK Experiment
    elif body["type"] == "attack.state":
        functions.run_ctk_experiement(body)
    # Resource attack (via SSM, usually)
    elif body["type"] == "attack.resource":
        functions.run_resource_attack(body)
    # Do an service scan
    elif body["type"] == "scan":
        functions.run_service_scan()
    # Generic wait step, used for testing
    elif body["type"] == "wait":
        functions.run_wait(body)
    else:
        logger.error(
            {
                "message": "Invalid event type: " + body["type"],
                "eventbridge_id": eventBridgeBody["id"],
            }
        )
        return False

    logger.debug(
        {
            "message": "Finished executing message from EventBridge.",
            "eventbridge_id": eventBridgeBody["id"],
        }
    )
    return True
