FROM ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive

RUN dpkg --add-architecture i386 \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        file \
        libasound2 \
        libc6:i386 \
        libfontconfig1 \
        libfreetype6 \
        libglib2.0-0 \
        libice6 \
        libncurses6:i386 \
        libsm6 \
        libstdc++6:i386 \
        libx11-6 \
        libxext6 \
        libxft2 \
        libxi6 \
        libxrender1 \
        libxss1 \
        libxtst6 \
        locales \
        make \
        python3 \
        tcl \
        unzip \
        xz-utils \
    && locale-gen en_US.UTF-8 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV LANG=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8

WORKDIR /workspace

CMD ["/bin/bash"]
