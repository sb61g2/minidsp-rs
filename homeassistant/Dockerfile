FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        libusb-1.0-0 \
        libhidapi-libusb0 \
        libudev1 \
        jq \
    && rm -rf /var/lib/apt/lists/*

# Binary is cross-compiled by CI and staged into this directory before docker build
COPY minidspd /usr/local/bin/minidspd
COPY run.sh /run.sh
RUN chmod +x /usr/local/bin/minidspd /run.sh

CMD ["/run.sh"]
