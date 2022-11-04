.PHONY: build deploy update

local:
	bash ./local.sh
	
build:
	pip install -r requirements.txt
	rm -f latest.zip
	mkdir -p build
	cp ./functions.py ./build/functions.py
	cp ./event_service.py ./build/event_service.py
	cp ./main.py ./build/main.py
	cp -rf ./venv/lib/python3.9/site-packages/* build
	cd ./build; zip -r ../latest.zip .

deploy-dev: build
	aws s3 cp ./latest.zip s3://firedrill-downloads-dev-downloads/modules/runner/latest.zip --acl public-read

update: build
	# Update the existing function with the latest code
	aws lambda update-function-code --function-name  firedrill-runner-default --zip-file fileb://latest.zip --profile firedrill-sandbox --region us-east-1