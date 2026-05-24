# Native IronSpec build on Ubuntu 20.04 x86_64

Reproducing the cross-tool evaluation with the real IronSpec executable
instead of the Python reproduction.

The Docker build of IronSpec from this repository did not complete under
x86 emulation on Apple Silicon. IronSpec was built for Ubuntu 20.04 on
x86_64 CloudLab nodes (Clemson cluster). Running it in that environment
removes the build problem.

## Cloud instance specification

- Provider: AWS EC2 (or equivalent)
- Image: Ubuntu Server 20.04 LTS (HVM), SSD volume type, **x86_64**
- Instance type: `c6i.large` or larger (2 vCPU, 4 GiB RAM minimum;
  4 vCPU / 8 GiB recommended for faster .NET builds)
- Storage: 30 GiB EBS gp3
- Security group: allow inbound SSH (port 22) from your IP

## Setup script

After SSH'ing in (`ssh -i key.pem ubuntu@<public-ip>`), run:

```bash
#!/bin/bash
set -euxo pipefail

# 1. Install IronSpec dependencies (from setup/node_prep.sh, pruned of gem5 cruft).
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
    git wget unzip ca-certificates apt-transport-https \
    build-essential openjdk-13-jdk \
    g++-8 g++-8-multilib \
    libprotobuf-dev protobuf-compiler libprotoc-dev \
    curl gnupg zlib1g-dev
sudo update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-8 20
sudo update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-8 20

# 2. Install dotnet-6 (from setup/install_dotnet_ubuntu_20.04.sh).
wget -q https://packages.microsoft.com/config/ubuntu/20.04/packages-microsoft-prod.deb \
     -O packages-microsoft-prod.deb
sudo dpkg -i packages-microsoft-prod.deb
sudo apt-get update
sudo apt-get install -y dotnet-sdk-6.0 aspnetcore-runtime-6.0 dotnet-runtime-6.0

# 3. Clone IronSpec and build the modified Dafny.
cd ~
git clone https://github.com/GLaDOS-Michigan/IronSpec.git
cd IronSpec
# DafnyVerifier.cs has a "username" placeholder; replace with the SSH user.
sed -i "s/username/$(whoami)/g" Source/Dafny/DafnyVerifier.cs
make exe
make z3-ubuntu

# 4. Smoke test: ASC mode on bundled sortMethod.dfy.
./Binaries/Dafny /compile:0 /checkInputAndOutputSpecified \
    specs/sort/sortMethod.dfy 2>&1 | tee asc_smoke.txt
grep "FLAG(HIGH)" asc_smoke.txt && echo "ASC smoke test OK" || echo "ASC smoke FAILED"
```

Estimated runtime: 8–20 minutes on `c6i.large`, mostly dotnet restore +
build of the Dafny solution. The DafnyRuntimeJava gradle step that
hung under emulation runs in ~1 minute natively.

## Running the SpecLaunder cross-tool evaluation against real IronSpec

After the build succeeds, copy this repository's benchmark and attacks
directories to the instance:

```bash
# from the SpecLaunder repo on the local machine
scp -r -i key.pem attacks/ benchmark.json ubuntu@<public-ip>:~/SpecLaunder/
```

On the VM, run IronSpec ASC against each laundered file in the benchmark:

```bash
cd ~/SpecLaunder
for f in attacks/*.dfy; do
  echo "=== $f ==="
  ~/IronSpec/Binaries/Dafny /compile:0 /checkInputAndOutputSpecified "$f" \
    2>&1 | tee "$(basename $f .dfy)_asc.txt"
done
```

The HIGH-flag lines in each output file are IronSpec's ASC verdicts.
Compare against the reproduction's verdicts (in
`results_cross_tool_eval.txt`). Any divergence is a defect in the
reproduction.

## Optional: full mutation-testing mode

This requires the additional gRPC server (separate repo,
`IronSpec-dafny-grpc-server`, built with bazel-4.0.0). Its setup is in
`setup/configureIronSpec.sh`. Per the IronSpec README, single-node setup
works; the distributed CloudLab profile is for throughput, not
correctness.

## What this replaces in the SpecLaunder writeup

When IronSpec runs successfully on the VM and the ASC verdicts on the
benchmark are recorded, replace the "IronSpec ASC (reproduction)" column
in `results_cross_tool_eval.txt` and `README.md` with the real
IronSpec output. Note any divergence from the reproduction explicitly.
