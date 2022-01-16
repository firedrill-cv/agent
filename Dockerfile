FROM public.ecr.aws/lambda/python:3.8 

# K6
# RUN apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
# RUN echo "deb https://dl.k6.io/deb stable main" | tee /etc/apt/sources.list.d/k6.list
# RUN apt-get update
# RUN apt-get install k6

# ToxiProxy
# RUN wget -O toxiproxy-2.1.4.deb https://github.com/Shopify/toxiproxy/releases/download/v2.1.4/toxiproxy_2.1.4_amd64.deb
# RUN dpkg -i toxiproxy-2.1.4.deb

# Install Python dependencies
COPY ./requirements.txt ${LAMBDA_TASK_ROOT}/requirements.txt
COPY /libs ${LAMBDA_TASK_ROOT}/libs

RUN pip install -U -r  ${LAMBDA_TASK_ROOT}/requirements.txt
# RUN pip install --use-feature=in-tree-build -e ${LAMBDA_TASK_ROOT}/libs/chaostoolkit-k6

# Copy code
COPY ./main.py ./main.py
COPY ./functions.py ./functions.py
COPY ./mothership.py ./mothership.py
COPY ./queue_monitor.py ./queue_monitor.py

# Run the app
CMD ["main.run"]
