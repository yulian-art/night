#!/usr/bin/env bash
set -euo pipefail
recognizer_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${STAR_PYTHON:-python3}"
# Installs only when this explicit setup script is invoked.
"$python_bin" -m venv "$recognizer_dir/.venv"
"$recognizer_dir/.venv/bin/python" -m pip install -r "$recognizer_dir/requirements-dev.txt"
"$recognizer_dir/.venv/bin/python" "$recognizer_dir/scripts/generate_proto.py"
"$recognizer_dir/.venv/bin/python" "$recognizer_dir/scripts/fetch_model.py"
echo "Ready: cd $recognizer_dir"
echo ".venv/bin/python -m star_recognizer doctor"
