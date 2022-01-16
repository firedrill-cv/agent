RUN LOCALLY:
1. Make sure the environment variables in `./local.sh` match a real, deployed runner!
2. Run  `./local.sh`


#### Test invocation
Use examples in events/invoke_examples.http or the Insomnia collection to test.

#### Send killswitch event
aws sqs send-message --queue-url https://queue.amazonaws.com/405409719858/firedrill-queue-8d7ea2e8-7663-11ec-804e-784f4371f2e3 --message-body '{"type": "killswitch"}'

SETUP VENV:
virtualenv venv
source venv/bin/activate

DEPLOY:
./deploy.sh