# Native IronSpec build on macOS (Apple Silicon and Intel)

An alternative to the AWS Linux path: build IronSpec directly on macOS,
using Rosetta 2 to run the bundled x86_64 z3 binary on Apple Silicon.
Targets ASC mode only (no gRPC server). Mutation-testing mode requires
bazel-4.0.0 and is a separate setup.

## Prerequisites

- **Apple Silicon (M-series) Mac:** ensure Rosetta 2 is installed.
  ```bash
  /usr/bin/pgrep oahd >/dev/null || softwareupdate --install-rosetta --agree-to-license
  ```
- **Intel Mac:** Rosetta not required.

## Setup

```bash
#!/bin/bash
set -euo pipefail

# 1. Install build dependencies via Homebrew.
#    openjdk@13 is no longer in homebrew core; openjdk@11 is the closest
#    compatible version that exists today and works for IronSpec's build.
#    dotnet@6 is not in homebrew core either; install via Microsoft channel.
brew install openjdk@11 wget unzip

# 2. Install dotnet-6 SDK directly from Microsoft (per their official
#    instructions). This places `dotnet` under ~/.dotnet/.
mkdir -p ~/.dotnet && cd ~/.dotnet
curl -L https://dot.net/v1/dotnet-install.sh -o dotnet-install.sh
chmod +x dotnet-install.sh
./dotnet-install.sh --channel 6.0 --install-dir ~/.dotnet
export PATH="$HOME/.dotnet:$PATH"
echo 'export PATH="$HOME/.dotnet:$PATH"' >> ~/.zshrc
dotnet --version  # should print 6.x.y

# 3. Clone IronSpec.
cd ~/Documents/GitHub  # or wherever
git clone https://github.com/GLaDOS-Michigan/IronSpec.git
cd IronSpec

# 4. Personalize the DafnyVerifier.cs "username" placeholder.
#    On macOS sed needs an empty -i argument.
sed -i '' "s/username/$USER/g" Source/Dafny/DafnyVerifier.cs

# 5. Build IronSpec's modified Dafny.
make exe

# 6. Fetch the macOS x86_64 z3 4.8.5 binary. On Apple Silicon this runs
#    via Rosetta 2 transparently.
make z3-mac

# 7. Smoke test: run ASC mode on the bundled sortMethod.dfy. The
#    expected output line is:
#      -- FLAG(HIGH) -- : NONE of Ensures depend on Any input parameters
./Binaries/Dafny /compile:0 /checkInputAndOutputSpecified \
    specs/sort/sortMethod.dfy 2>&1 | tee /tmp/asc_smoke.txt
grep "FLAG(HIGH)" /tmp/asc_smoke.txt && echo "ASC smoke test OK" || \
    { echo "ASC smoke FAILED — inspect /tmp/asc_smoke.txt"; exit 1; }
```

## Required runtime arguments — observed empirically

The IronSpec README's ASC example understates the required arguments.
Empirically, real ASC requires all of the following:

- `DOTNET_ROOT=$HOME/.dotnet` (env var, since dotnet was installed there)
- `/compile:0`
- `/checkInputAndOutputSpecified`
- `/mutationTarget:<predicate_name>`  — a predicate/function name to mutate;
  must be module-qualified (e.g., `sortSpec.SortSpec`) to avoid a
  `StartIndex cannot be less than zero` exception in
  `GetFunctionFromUnresolved` at `SpecInputOutputChecker.cs:2632`
- `/mutationRootName:<predicate_name>`  — typically same as mutationTarget
- `/proofName:<module.method>`  — the method to apply ASC to
- `/proofLocation:<absolute_path_to_dfy>`
- `/serverIpPortList:ipPorts.txt`  — a file with `127.0.0.1:50051` is
  accepted by the input-dependency portion of ASC even without an
  actual gRPC server running
- `<absolute_path_to_dfy>` as the final positional argument

Note: the IronSpec error message names the flag as `/holeEvalServerIpPortList`
but the actual flag accepted by DafnyOptions.cs is `/serverIpPortList`.

## Verified smoke-test invocation

```bash
cd ~/Documents/GitHub/spec-laundering/IronSpec
echo "127.0.0.1:50051" > ipPorts.txt
./Binaries/Dafny /compile:0 /checkInputAndOutputSpecified \
    /mutationTarget:sortSpec.SortSpec \
    /mutationRootName:sortSpec.SortSpec \
    /proofName:sort.merge_sort \
    /proofLocation:"$(pwd)/specs/sort/sortMethod.dfy" \
    /serverIpPortList:ipPorts.txt \
    "$(pwd)/specs/sort/sortMethod.dfy"
```

Expected output includes:

```
-- FLAG(HIGH) -- : NONE of Ensures depend on Any input parameters
-- FLAG(Medium) -- : Only some parts of output (output) are constrained by the post conditions
```

The HIGH flag matches what the Python reproduction
(`detector/ironspec_asc_repro.py`) reports for the same input. The
Medium flag is the output-coverage portion that the reproduction
explicitly does not implement.

## Running real IronSpec ASC on the SpecLaunder benchmark

This requires per-attack restructuring of the attack files. IronSpec's
ASC expects the spec to be a named predicate in a module, separate from
the method's inline `ensures` clauses. The SpecLaunder attack files use
inline ensures (which the Python reproduction handles directly but ASC
does not). Restructuring each attack into a module + spec predicate
layout is a follow-up task.

Full output of the bundled-spec smoke test is saved as
`results_real_ironspec_sortmethod.txt`.

## Known risks on macOS

- `openjdk@11` is used in place of `openjdk@13` (which is not in
  Homebrew core). IronSpec's Dafny solution may have version warnings
  but the build should succeed.
- `dotnet-6` is installed via Microsoft's installer rather than
  Homebrew. The `dotnet@8` cask Homebrew offers will not work — IronSpec
  pins to .NET 6.
- The `make z3-mac` target downloads an x86_64 macOS binary. On Apple
  Silicon, Rosetta 2 must be installed for it to run.
- Mutation-testing mode requires bazel-4.0.0 and the
  `IronSpec-dafny-grpc-server` repo; not covered here.

## Fallback

If the native macOS build fails after a real attempt, see
`aws_ironspec_setup.md` for the Ubuntu 20.04 path. The Ubuntu path is
what IronSpec was built and tested against; macOS is an unsupported
configuration that happens to be feasible due to .NET's portability and
Rosetta 2 translation.
