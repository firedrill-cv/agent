import signal
import os
import functions
import mothership
from logzero import logger


class GracefulKiller:
    kill_now = False
    signals = {
        signal.SIGINT: 'SIGINT',
        signal.SIGTERM: 'SIGTERM'
    }

    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, signum, frame):
        print("\nReceived {} signal".format(self.signals[signum]))
        print("Cleaning up resources. End of the program")
        self.kill_now = True


def run(body, context):
    # Ensure all of the required fields are provided
    if body == None or "type" not in body:
        raise KeyError("No 'type' parameter in body.")
    elif body["payload"] == None:
        raise KeyError("No 'payload' parameter in body.")

    # Payload is there, figure out what to do with it
    else:
        # Check signature
        disable_signing = os.environ.get("DISABLE_SIGNING")
        if disable_signing and disable_signing == "true":
            logger.debug({
                "message": "SKIPPING SIGNATURE VERIFICATION"
            })
            verified = True
        else:
            signature = body["signature"]
            del body["signature"]
            verified = mothership.verifySignature(signature, body)

        if verified == False:
            print('Invalid signature, not running.')
            return {
                "success": False,
                "reason": "Invalid signature."
            }

        # CTK Experiment
        elif body["type"] == "attack.state":
            functions.run_ctk_experiement(body)

        # Resource attack (via SSM, usually)
        elif body["type"] == "attack.resource":
            functions.run_resource_attack(body)

        # Do an inventory scan
        elif body["type"] == "scan.inventory":
            functions.run_service_scan(body)
        else:
            print("Invalid event type: " + body["type"])
            return {
                "success": False,
                "reason": "Invalid event type."
            }

    print('Processing complete.')
    return {
        "success": True,
    }
