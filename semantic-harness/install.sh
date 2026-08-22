#!/bin/bash
set -e

echo "==================================="
echo " Installing Semantic-Harness"
echo "==================================="

echo ">>> Installing Python Dependencies..."
cd python
# Use venv for isolated testing
python3 -m venv .venv
source .venv/bin/activate
# Install current directory in editable mode
pip install -e .
cd ..

echo ">>> Installing NPM Dependencies..."
cd npm
npm install
# Ensure zod is installed for C2CSemantics
npm install zod
cd ..

echo "==================================="
echo " Installation Complete!"
echo "==================================="
