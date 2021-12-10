import http.client
import os
import json
from datetime import datetime
import hmac
import hashlib

mothership_url = os.environ.get('MOTHERSHIP_URL')
runner_id = os.environ.get('RUNNER_ID')
runner_key = os.environ.get('RUNNER_KEY')


def signRequest(payload: dict) -> str:
    return hmac.new(runner_key.encode(
        "utf-8"), json.dumps(payload).encode("utf-8"), hashlib.sha256).hexdigest()


def verifySignature(signature: str, payload: dict) -> bool:
    expected = hmac.new(runner_key.encode(
        "utf-8"), json.dumps(payload).encode("utf-8"), hashlib.sha256).hexdigest()

    if signature != expected:
        print('Signature verification failed - signature doesn\'t match what was provided')
        print('Provided: {}'.format(signature))
        print('Expected: {}'.format(expected))
        print('Payload: {}'.format(payload))
        print(runner_key)
        return False

    print('Signature verification success.')
    return True


def get_event_url(execution_id: str):
    return 'https://{mothership_url}/executions/{execution_id}/events'.format(
        mothership_url=mothership_url,
        execution_id=execution_id
    )


def get_pending_item() -> object:
    print('Getting next pending queue item ...')

    connection = http.client.HTTPSConnection(mothership_url)
    connection.request("GET", "/queue", None, {
        "x-agent-id": runner_id,
        "x-agent-signature": signRequest({
            "runner_id": runner_id
        })
    })
    response = connection.getresponse()

    if (response.status != 200):
        print("ERROR!!! Status: {} and reason: {}".format(
            response.status, response.reason))
        return None

    payload = json.loads(response.read().decode())
    return payload


def send_toolkit_event(execution_id: str, execution_token: str, name: str, phase: str, payload: object):
    event = {
        "execution_id": execution_id,
        "execution_token": execution_token,
        'name': name,
        'payload': payload,
        'phase': phase,
        'ts': datetime.timestamp(datetime.now()),
    }
    print(event)
    connection = http.client.HTTPSConnection(mothership_url)
    connection.request("POST", "/executions/{execution_id}/events".format(
        execution_id=execution_id
    ), json.dumps(event),
        {
            'Content-type': 'application/json',
            'x-execution-token': execution_token
    })

    response = connection.getresponse()
    if (response.status != 200):
        print("Failed to send toolkit event!!! ")
        print("Status: {} and reason: {}".format(
            response.status, response.reason))
    return
