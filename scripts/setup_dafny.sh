#!/usr/bin/env bash
# Install Dafny 4.11.0 (self-contained, bundles Z3) if not already on PATH.
# Idempotent: no-op when `dafny` is available.
set -e

if command -v dafny >/dev/null 2>&1; then
  exit 0
fi

URL="https://github.com/dafny-lang/dafny/releases/download/v4.11.0/dafny-4.11.0-x64-ubuntu-22.04.zip"
TMP="$(mktemp -d)"
curl -sL -o "$TMP/dafny.zip" "$URL"
unzip -q -o "$TMP/dafny.zip" -d /opt
ln -sf /opt/dafny/dafny /usr/local/bin/dafny
rm -rf "$TMP"

dafny --version
