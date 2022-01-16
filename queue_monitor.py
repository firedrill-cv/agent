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
        print('No messages in the SQS queue.')
        return

    messages = response["Messages"]
    message = messages[0]

    if "Body" not in message:
        print("Body not in message")
        print(message)
        return

    message_body = json.loads(message['Body'])

    print("MESSAGE BODY:")
    print(message_body)

    type = message_body['type']

    sqs.delete_message(
        QueueUrl=queue_url,
        ReceiptHandle=message['ReceiptHandle']
    )
    print("Deleted message from queue")

    print('TYPE: {}'.format(type))

    if type == "killswitch":
        print("Received killswitch, terminating.")
        stop_watching_queue()
        functions.send_event(test_suite_run_step_id, "stopped", message_body)
        sys.exit(0)


def start_watching_queue(test_suite_run_step_id):
    print("Start watching queue...")
    monitor = sqs_monitor(test_suite_run_step_id)


def stop_watching_queue():
    if monitor is None:
        print("Watcher already closed.")
    else:
        print("Stop watching queue...")
        try:
            monitor()
        except Exception as ex:
            print("Failed to stop watcher! Error thrown!")
            print(str(ex))
