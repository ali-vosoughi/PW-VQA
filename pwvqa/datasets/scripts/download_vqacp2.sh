#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
mkdir -p "$repo_root/data/vqa"
cd "$repo_root/data/vqa"
wget http://data.lip6.fr/cadene/murel/vqacp2.tar.gz
tar -xzvf vqacp2.tar.gz
