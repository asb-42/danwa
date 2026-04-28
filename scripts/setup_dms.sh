#!/usr/bin/env bash
set -e

echo "Installing DMS dependencies..."
if [ "$1" = "--gpu" ]; then
    uv pip install paddlepaddle-gpu paddleocr
else
    uv pip install paddlepaddle paddleocr
fi
echo "DMS dependencies installed."
