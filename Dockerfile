FROM python:3.6-bullseye

RUN apt-get update && apt-get install -y git wget curl

WORKDIR /root

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY docker-entrypoint.sh /

COPY . .
RUN make setup-config

ENTRYPOINT ["/docker-entrypoint.sh"]
