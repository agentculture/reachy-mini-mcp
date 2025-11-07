#!/bin/bash
# Setup script to download a default Piper TTS model

set -e

echo "================================"
echo "Piper TTS Model Setup"
echo "================================"
echo ""

# Default model directory
MODEL_DIR="$HOME/.local/share/piper/models"
mkdir -p "$MODEL_DIR"

echo "📁 Model directory: $MODEL_DIR"
echo ""

# Suggest a lightweight English model
MODEL_NAME="en_US-lessac-medium"
MODEL_URL="https://github.com/rhasspy/piper/releases/download/v1.2.0/${MODEL_NAME}.onnx"
MODEL_JSON_URL="https://github.com/rhasspy/piper/releases/download/v1.2.0/${MODEL_NAME}.onnx.json"

MODEL_PATH="$MODEL_DIR/${MODEL_NAME}.onnx"
MODEL_JSON_PATH="$MODEL_DIR/${MODEL_NAME}.onnx.json"

# Check if model already exists
if [ -f "$MODEL_PATH" ]; then
    echo "✓ Model already exists: $MODEL_PATH"
    echo ""
    echo "To use this model, run:"
    echo "  export PIPER_MODEL=$MODEL_PATH"
    echo ""
    echo "Or add to your ~/.bashrc:"
    echo "  echo 'export PIPER_MODEL=$MODEL_PATH' >> ~/.bashrc"
    exit 0
fi

echo "📥 Downloading model: $MODEL_NAME"
echo "   This may take a few minutes..."
echo ""

# Download model file
echo "Downloading model file..."
wget -q --show-progress "$MODEL_URL" -O "$MODEL_PATH" || {
    echo "❌ Failed to download model file"
    exit 1
}

# Download model config
echo "Downloading model config..."
wget -q --show-progress "$MODEL_JSON_URL" -O "$MODEL_JSON_PATH" || {
    echo "❌ Failed to download model config"
    exit 1
}

echo ""
echo "✅ Model installed successfully!"
echo ""
echo "Model location: $MODEL_PATH"
echo ""
echo "To use this model:"
echo "  export PIPER_MODEL=$MODEL_PATH"
echo ""
echo "To make it permanent, add to your ~/.bashrc:"
echo "  echo 'export PIPER_MODEL=$MODEL_PATH' >> ~/.bashrc"
echo "  source ~/.bashrc"
echo ""
echo "================================"
