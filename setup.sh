#!/usr/bin/env bash
set -e

echo "📦 Installiere uv & dependencies..."
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

echo "🐍 Erstelle Umgebung..."
uv venv .venv --python 3.11
source .venv/bin/activate
uv pip install -e .

echo "📁 Verzeichnisse & Config..."
mkdir -p logs config/prompts
echo "✅ Setup abgeschlossen. Starte mit: bash scripts/start.sh"