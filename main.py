from logging import log
import signal
import threading
import functions
import time
from logzero import logger
import queue_monitor


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
        queue_monitor.stop_watching_queue()
        print("Cleaning up resources. End of the program")
        self.kill_now = True


def run(body, context):

    queue_monitor.start_watching_queue()

    # Ensure all of the required fields are provided
    if body == None or "type" not in body:
        raise KeyError("No 'type' parameter in body.")
    elif body["payload"] == None:
        raise KeyError("No 'payload' parameter in body.")

    # Payload is there, figure out what to do with it
    else:
        # CTK Experiment
        if body["type"] == "attack.state":
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
            print("Invalid event type: " + body["type"])

    print('Processing complete.')
    queue_monitor.stop_watching_queue()
    return {
        "success": True,
    }
