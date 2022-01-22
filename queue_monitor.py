import threading
import boto3
import sched
import time
import os
import json
import sys
import functions

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
    sqs = boto3.client('sqs')
    queue_url = os.environ.get("SQS_URL")
    print("Checking SQS Queue: {}".format(queue_url))
    response = sqs.receive_message(
        QueueUrl=queue_url,
        AttributeNames=[
            'All'
        ],
        MaxNumberOfMessages=1,
    )

    # print("SQS Queue response:")
    # print(response)

    if "Messages" not in response or len(response["Messages"]) == 0:
        print('[QUEUE] No messages in the SQS queue.')
        return

    messages = response["Messages"]
    message = messages[0]

    if "Body" not in message:
        print("[QUEUE] Body not in message, ignoring.")
        print(message)
        return

    message_body = json.loads(message['Body'])

    type = message_body['type']

    sqs.delete_message(
        QueueUrl=queue_url,
        ReceiptHandle=message['ReceiptHandle']
    )
    print("[QUEUE] Deleted message from queue")

    print('[QUEUE] Message type: {}'.format(type))

    if type == "killswitch":
        print("[QUEUE] Received killswitch, terminating.")
        stop_watching_queue()
        functions.send_event(test_suite_run_step_id, "stopped", message_body)
        sys.exit(0)


def start_watching_queue(test_suite_run_step_id):
    print("[QUEUE] Starting watcher...")
    monitor = sqs_monitor(test_suite_run_step_id)


def stop_watching_queue():
    if t is not None:
        t.stop()
    if monitor is None:
        print("[QUEUE] Watcher was already closed.")
    else:
        print("[QUEUE] Stopping watcher...")
        try:
            monitor()
            print("[QUEUE] Watcher stopped successfully.")
        except Exception as ex:
            print("[QUEUE] Failed to stop watcher!")
            print(str(ex))
