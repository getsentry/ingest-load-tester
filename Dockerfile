FROM python:3.13-slim

RUN apt-get update \
    && apt-get install --no-install-recommends -y git wget curl ca-certificates build-essential python3-dev libev-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install and setup UV
# Download the latest installer
ADD https://astral.sh/uv/install.sh /uv-installer.sh

# Run the installer then remove it
RUN sh /uv-installer.sh && rm /uv-installer.sh

COPY docker-entrypoint.sh /

# Copy application code and build dependencies.
COPY . .
RUN /root/.local/bin/uv sync

# Create config stubs
RUN make setup-config

ENTRYPOINT ["/docker-entrypoint.sh"]
