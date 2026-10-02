#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
backend="${1:-cpu}"
case "$backend" in
  cpu) requirements="$repo_root/requirements.txt" ;;
  cu128) requirements="$repo_root/requirements-cu128.txt" ;;
  *) echo "Usage: bash scripts/setup.sh [cpu|cu128]" >&2; exit 2 ;;
esac

if ! command -v uv >/dev/null 2>&1 || [[ "$(uv --version)" != "uv 0.8.17"* ]]; then
  echo "Install the setup tool first: python -m pip install uv==0.8.17" >&2
  exit 2
fi
uv python install 3.9.23
venv_dir="${PWVQA_VENV:-$repo_root/.venv}"
if [[ ! -f "$venv_dir/pyvenv.cfg" ]]; then
  uv venv --python 3.9.23 "$venv_dir"
fi
if [[ -x "$venv_dir/bin/python" ]]; then
  env_python="$venv_dir/bin/python"
elif [[ -f "$venv_dir/Scripts/python.exe" ]]; then
  env_python="$venv_dir/Scripts/python.exe"
else
  echo "No Python found in $venv_dir" >&2
  exit 2
fi
# Bootstrap invokes python and pip in child processes during model runs.
export PATH="$(dirname -- "$env_python"):$PATH"
"$env_python" -c 'import platform, sys; assert sys.version_info[:3] == (3, 9, 23), "Use Python 3.9.23"; assert (sys.platform, platform.machine()) in [("linux", "x86_64"), ("win32", "AMD64")], "Locks support Linux/Windows x86-64"'
uv pip sync --python "$env_python" --torch-backend "$backend" \
  --index-strategy unsafe-best-match \
  --build-constraints "$repo_root/requirements-build.txt" "$requirements"
"$env_python" scripts/apply_patches.py
"$env_python" scripts/smoke_test.py
uv pip check --python "$env_python"
echo "Setup verified ($backend). Activate $venv_dir/bin/activate on Linux or $venv_dir/Scripts/activate in Git Bash."
