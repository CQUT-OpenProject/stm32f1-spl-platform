FROM ubuntu:24.04@sha256:fe81560990fae86dc4743202b2cb4d3df98d0bcf949173cecef15ce1127ef852

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    gcc-arm-none-eabi=15:13.2.rel1-2 \
    libnewlib-arm-none-eabi=4.4.0.20231231-2 \
    clang=1:18.0-59~exp2 \
    lld=1:18.0-59~exp2 \
    clang-18=1:18.1.3-1ubuntu1 lld-18=1:18.1.3-1ubuntu1 \
    binutils-arm-none-eabi cmake make ninja-build git openssh-client python3 \
    gdb-multiarch openocd ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace/stm32f1-spl-platform
CMD ["bash"]
