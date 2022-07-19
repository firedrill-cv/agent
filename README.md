## Developing
### Run locally
1. Go into venv:
`source ./venv/bin/activate`
2. Make sure the environment variables in `./local.sh` match a real, deployed runner and SQS queue!
3. Run  `./local.sh`

### Deploy to S3
Run `make deploy`

#### Test invocation
Use examples in events/invoke_examples.http or the Insomnia collection to test.

#### Send killswitch event
aws sqs send-message --queue-url https://sqs.us-east-1.amazonaws.com/405409719858/firedrill-runner-messages.fifo --region us-east-1 --message-group-id 14fgf5 --message-deduplication-id g3fgf4 --message-body '{
        "type": "killswitch",
        "target": "runner",
        "id": "88a77c14-aeed-11ec-9fa7-784f4371f2e3"
    }'


DEPLOY:
./deploy.sh