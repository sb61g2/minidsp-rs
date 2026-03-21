ARG BUILD_FROM
FROM $BUILD_FROM

ARG BUILD_ARCH

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
        libusb-1.0-0 \
        libhidapi-libusb0 \
        libudev1 \
        curl \
        jq \
    && rm -rf /var/lib/apt/lists/*

# Download minidspd binary from latest GitHub release
RUN set -eux \
    && case "${BUILD_ARCH}" in \
         amd64)       TRIPLE="x86_64-unknown-linux-gnu" ;; \
         aarch64)     TRIPLE="aarch64-unknown-linux-gnu" ;; \
         armv7|armhf) TRIPLE="arm-linux-gnueabihf-rpi" ;; \
         *) echo "Unsupported architecture: ${BUILD_ARCH}" && exit 1 ;; \
       esac \
    && RELEASE_TAG=$(curl -fsSL "https://api.github.com/repos/mrene/minidsp-rs/releases/latest" \
         | jq -r '.tag_name') \
    && echo "Downloading minidspd ${RELEASE_TAG} for ${TRIPLE}" \
    && curl -fsSL \
         "https://github.com/mrene/minidsp-rs/releases/download/${RELEASE_TAG}/minidsp.${TRIPLE}.tar.gz" \
         | tar -xz -C /usr/local/bin/ minidspd \
    && chmod +x /usr/local/bin/minidspd

COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
