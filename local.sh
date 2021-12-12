AWS_ACCESS_KEY_ID=$(aws --profile chinchilla-sandbox configure get aws_access_key_id)
AWS_SECRET_ACCESS_KEY=$(aws --profile chinchilla-sandbox configure get aws_secret_access_key)

docker build . -t chinchilla-runner

docker run -it --rm -p 9000:8080  \
    -e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
    -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
    -e AWS_DEFAULT_REGION=us-east-1 \
    -e DISABLE_SIGNING=true \
    chinchilla-runner