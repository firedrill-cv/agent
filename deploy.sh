docker build -t firedrill-runner .

# Push the public image
aws ecr-public get-login-password --region us-east-1 | docker login --username AWS --password-stdin public.ecr.aws/t6n5j8n8xs
docker tag firedrill-runner:latest public.ecr.aws/t6n5j8n8/firedrill-runner:latest
docker push public.ecr.aws/t6n5j8n8/firedrill-runner:latest

# docker tag firedrill-runner:latest adamdabbracci/firedrill-runner:latest
# docker push adamdabbracci/firedrill-runner:latest