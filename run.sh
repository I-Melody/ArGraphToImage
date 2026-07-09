#!/bin/bash
# Launch script for Ar3 Annotation Workbench
# Sets up required shared library paths for Qt WebEngine

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="${SCRIPT_DIR}/.venv/shared-libs"
QT_LIB_DIR="${SCRIPT_DIR}/.venv/lib/python3."*"/site-packages/PyQt6/Qt6/lib"

# Extract .deb packages if needed
if [ ! -d "$LIB_DIR" ]; then
    echo "[Ar3] Extracting system libraries..."
    mkdir -p "$LIB_DIR"
    cd "$LIB_DIR" || exit 1
    for pkg in libnspr4 libnss3 libasound2t64 libxkbfile1 libxcomposite1 libxdamage1 libxrandr2 libxtst6; do
        if apt download "$pkg" 2>/dev/null; then
            for deb in "$pkg"*.deb; do
                dpkg-deb -x "$deb" . 2>/dev/null
            done
        fi
    done
    cd "$SCRIPT_DIR" || exit 1
    echo "[Ar3] Libraries extracted."
fi

export LD_LIBRARY_PATH="${LIB_DIR}/usr/lib/x86_64-linux-gnu:${QT_LIB_DIR}:${LD_LIBRARY_PATH}"

source "${SCRIPT_DIR}/.venv/bin/activate"
python "${SCRIPT_DIR}/main.py" "$@"
