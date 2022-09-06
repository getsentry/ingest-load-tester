FROM python:3.8-slim

RUN apt-get update \
    && apt-get install --no-install-recommends -y git wget curl build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /root

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY docker-entrypoint.sh /

COPY . .
RUN make setup-config

ENTRYPOINT ["/docker-entrypoint.sh"]
