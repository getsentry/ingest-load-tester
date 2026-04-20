FROM python:3.13-slim

RUN apt-get update \
    && apt-get install --no-install-recommends -y git wget curl build-essential python3-dev libev-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY docker-entrypoint.sh /

COPY . .
RUN make setup-config

ENTRYPOINT ["/docker-entrypoint.sh"]
