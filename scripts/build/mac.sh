#!/bin/bash
# Build macOS executable using PyInstaller

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PACKAGE_DIR="$PROJECT_ROOT/package"
RESOURCES_DIR="$PACKAGE_DIR/resources/mac"
SPEC_FILE="$SCRIPT_DIR/mac.spec"

mkdir -p "$RESOURCES_DIR"

if ! command -v pyinstaller &> /dev/null; then
    pip install pyinstaller
fi

cd "$SCRIPT_DIR"
pyinstaller --clean "$SPEC_FILE"

OUTPUT_BIN="$SCRIPT_DIR/dist/compress-image"
if [ -f "$OUTPUT_BIN" ]; then
    cp "$OUTPUT_BIN" "$RESOURCES_DIR/"
    chmod +x "$RESOURCES_DIR/compress-image"
    echo "macOS build complete: $RESOURCES_DIR/compress-image"
else
    echo "Error: PyInstaller did not produce expected output" >&2
    exit 1
fi