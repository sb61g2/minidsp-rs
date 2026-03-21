# Build stage — compiles minidspd from the full repo source
FROM rust:slim-bookworm AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        pkg-config \
        libusb-1.0-0-dev \
        libhidapi-dev \
        libudev-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY . .
RUN cargo build --release --bin minidspd \
    && strip target/release/minidspd

# Runtime stage
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        libusb-1.0-0 \
        libhidapi-libusb0 \
        libudev1 \
        jq \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /build/target/release/minidspd /usr/local/bin/minidspd
COPY homeassistant/run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
