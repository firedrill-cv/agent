
# Via Docker: Push the public image
# docker build -t firedrill-runner .
# aws ecr-public get-login-password --region us-east-1 | docker login --username AWS --password-stdin public.ecr.aws/t6n5j8n8xs
# docker tag firedrill-runner:latest public.ecr.aws/t6n5j8n8/firedrill-runner:latest
# docker push public.ecr.aws/t6n5j8n8/firedrill-runner:latest

# Via S3: Push a zipped version to S3
make