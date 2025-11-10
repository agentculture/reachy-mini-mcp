#!/bin/bash
# Build script for Reachy Hearing Service Docker image

set -e

# Configuration
IMAGE_NAME="reachy-hearing-thor"
IMAGE_TAG="r38.2.arm64-sbsa-cu130-24.04"
FULL_IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"

echo "================================================"
echo "Building Reachy Hearing Service Docker Image"
echo "================================================"
echo ""
echo "Image: ${FULL_IMAGE}"
echo ""

# Check if we're in the right directory
if [ ! -f "Dockerfile" ]; then
    echo "ERROR: Dockerfile not found!"
    echo "Please run this script from the hearing_app directory"
    exit 1
fi

# Build the image
echo "Building Docker image..."
docker build -t "${FULL_IMAGE}" .

if [ $? -eq 0 ]; then
    echo ""
    echo "================================================"
    echo "✓ Build successful!"
    echo "================================================"
    echo ""
    echo "Image: ${FULL_IMAGE}"
    echo ""
    echo "Next steps:"
    echo "  1. Start the service:"
    echo "     docker-compose -f ../docker-compose-vllm.yml up -d reachy-hearing"
    echo ""
    echo "  2. View logs:"
    echo "     docker logs -f reachy-hearing-service"
    echo ""
    echo "  3. Test connection:"
    echo "     nc -U /tmp/reachy_sockets/hearing.sock"
    echo ""
else
    echo ""
    echo "================================================"
    echo "✗ Build failed!"
    echo "================================================"
    exit 1
fi
