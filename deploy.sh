aws ecr-public get-login-password --region us-east-1 | docker login --username AWS --password-stdin public.ecr.aws/t6n5j8n8

docker build -t chinchilla-runner .

docker tag chinchilla-runner:latest public.ecr.aws/t6n5j8n8/chinchilla-runner:latest
docker push public.ecr.aws/t6n5j8n8/chinchilla-runner:latest

docker tag chinchilla-runner:latest adamdabbracci/chinchilla-runner:latest
docker push adamdabbracci/chinchilla-runner:latest