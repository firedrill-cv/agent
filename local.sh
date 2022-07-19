AWS_ACCESS_KEY_ID=$(aws --profile firedrill-sandbox configure get aws_access_key_id)
AWS_SECRET_ACCESS_KEY=$(aws --profile firedrill-sandbox configure get aws_secret_access_key)

docker build . -t firedrill-runner

docker run -it --rm -p 9000:8080  \
    -e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
    -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
    -e AWS_DEFAULT_REGION=us-east-1 \
    -e SQS_URL=https://queue.amazonaws.com/405409719858/firedrill-queue-8d7ea2e8-7663-11ec-804e-784f4371f2e3 \
    -e RUNNER_ID=3bf5bbee-ce26-11ec-bbc1-62f4d09b8cd6 \
    -e RUNNER_KEY=snqRLi8IVGJ0QEzK3ON9RFbXLmFpPt6xYxsHc1IRbwvNaZ4jRm \
    firedrill-runner