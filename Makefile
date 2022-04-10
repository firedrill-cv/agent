deploy:
	pip install -r requirements.txt
	rm -f latest.zip
	mkdir -p build
	cp ./functions.py ./build/functions.py
	cp ./queue_monitor.py ./build/queue_monitor.py
	cp ./event_service.py ./build/event_service.py
	cp ./main.py ./build/main.py
	cp -rf ./venv/lib/python3.9/site-packages/* build
	cd ./build; zip -r ../latest.zip .
	aws s3 cp ./latest.zip s3://code.dev.firedrill.sh/modules/runner/latest.zip --acl public-read