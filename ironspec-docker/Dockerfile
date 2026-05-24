# IronSpec (Goldweber et al., USENIX OSDI 2024) containerized for cross-tool
# evaluation. Targets Ubuntu 20.04 + x86_64 (the bundled z3 4.8.5 binary is
# x64-only); built as linux/amd64 under emulation on non-x86 hosts.
#
# Phase 1 (this image): dotnet-6, IronSpec Dafny build, z3 4.8.5  -> ASC mode.
# Phase 2 (interactive): bazel, protobuf, gRPC server build       -> mutation mode.
FROM --platform=linux/amd64 ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

RUN apt-get update && apt-get install -y --no-install-recommends \
        wget unzip git ca-certificates apt-transport-https \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# IronSpec lists openjdk-13; focal may not carry 13, fall back to 11.
RUN apt-get update \
    && (apt-get install -y --no-install-recommends openjdk-13-jdk \
        || apt-get install -y --no-install-recommends openjdk-11-jdk) \
    && rm -rf /var/lib/apt/lists/*

# dotnet-6 SDK (method per IronSpec/setup/install_dotnet_ubuntu_20.04.sh).
RUN wget -q https://packages.microsoft.com/config/ubuntu/20.04/packages-microsoft-prod.deb \
        -O packages-microsoft-prod.deb \
    && dpkg -i packages-microsoft-prod.deb \
    && rm packages-microsoft-prod.deb \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        dotnet-sdk-6.0 aspnetcore-runtime-6.0 dotnet-runtime-6.0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt
RUN git clone --depth 1 https://github.com/GLaDOS-Michigan/IronSpec.git

WORKDIR /opt/IronSpec
# DafnyVerifier.cs contains a "username" placeholder substituted at setup time.
RUN sed 's/username/root/g' Source/Dafny/DafnyVerifier.cs > /tmp/dv.cs \
    && mv /tmp/dv.cs Source/Dafny/DafnyVerifier.cs

RUN make exe
RUN make z3-ubuntu

# Phase 2 dependencies installed; gRPC server built interactively after image.
RUN apt-get update && apt-get install -y --no-install-recommends \
        g++-8 g++-8-multilib \
        libprotobuf-dev protobuf-compiler libprotoc-dev \
        curl gnupg zlib1g-dev \
    && update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-8 20 \
    && update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-8 20 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/IronSpec
CMD ["/bin/bash"]
