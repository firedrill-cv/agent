deploy:
	pip install -r requirements.txt
	rm -f build.zip
	mkdir -p build
	cp ./functions.py ./build/functions.py
	cp ./queue_monitor.py ./build/queue_monitor.py
	cp ./main.py ./build/main.py
	cp -rf ./venv/lib/python3.9/site-packages/* build
	cd ./build; zip -r ../build.zip .
	aws s3 cp ./build.zip s3://code.dev.firedrill.sh --acl public-read