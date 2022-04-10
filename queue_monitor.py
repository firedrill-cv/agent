import event_service
import threading
import boto3
import sched
import time
import os
import json
import sys
from logzero import logger

scheduler = sched.scheduler(time.time, time.sleep)
schedule_interval = 1
monitor = None
t = None


def setInterval(interval):
    def decorator(function):
        def wrapper(*args, **kwargs):
            stopped = threading.Event()

            def loop():  # executed in another thread
                while not stopped.wait(interval):  # until stopped
                    function(*args, **kwargs)

            t = threading.Thread(target=loop)
            t.daemon = True  # stop if the program exits
            t.start()
            return stopped

        return wrapper

    return decorator


@setInterval(schedule_interval)
def sqs_monitor(test_suite_run_step_id):
    sqs = boto3.client("sqs")
    account_id = boto3.client("sts").get_caller_identity().get("Account")
    queue_url = "https://sqs.{}.amazonaws.com/{}/firedrill-runner-messages.fifo".format(
        os.environ.get("AWS_REGION"),
        account_id,
    )
    response = sqs.receive_message(
        QueueUrl=queue_url,
        AttributeNames=["All"],
        MaxNumberOfMessages=1,
        WaitTimeSeconds=20,
    )

    if "Messages" not in response or len(response["Messages"]) == 0:
        logger.debug(
            {"run_step_id": test_suite_run_step_id, "message": "No messages in queue."}
        )
        return

    messages = response["Messages"]
    message = messages[0]

    if "Body" not in message:
        logger.error(
            {
                "run_step_id": test_suite_run_step_id,
                "message": "No Body in message, ignoring.",
            }
        )
        return

    message_body = json.loads(message["Body"])

    type = message_body["type"]

    sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=message["ReceiptHandle"])

    logger.debug({"run_step_id": test_suite_run_step_id, "message_type": type})

    if type == "killswitch":
        logger.debug(
            {
                "run_step_id": test_suite_run_step_id,
                "message": "KILLSWITCH! Stopping the queue monitor.",
            }
        )
        killswitch(test_suite_run_step_id, "stopped", message_body)


def start_watching_queue(test_suite_run_step_id):
    monitor = sqs_monitor(test_suite_run_step_id)


def killswitch(test_suite_run_step_id, status, message_body):
    stop_watching_queue()
    event_service.send_event(test_suite_run_step_id, status, message_body)
    sys.exit(0)


def stop_watching_queue():
    if t is not None:
        t.stop()
    else:
        logger.debug({"message": "Stopping queue watcher."})
        try:
            monitor()
            logger.debug({"message": "Stopped watching queue successfully.."})
        except Exception as ex:
            logger.error({"message": "Failed to stop watching the queue."})
