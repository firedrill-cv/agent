AWS_ACCESS_KEY_ID=$(aws --profile chinchilla-sandbox configure get aws_access_key_id)
AWS_SECRET_ACCESS_KEY=$(aws --profile chinchilla-sandbox configure get aws_secret_access_key)

docker build . -t chinchilla-runner

docker run -it --rm -p 9000:8080  \
    -e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
    -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
    -e AWS_DEFAULT_REGION=us-east-1 \
    -e DISABLE_SIGNING=true \
    -e RUNNER_ID=d8658f8e-1979-11ec-8334-784f4371f2e3 \
    -e RUNNER_KEY=snqRLi8IVGJ0QEzK3ON9RFbXLmFpPt6xYxsHc1IRbwvNaZ4jRm \
    chinchilla-runner