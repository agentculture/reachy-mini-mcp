FROM nvcr.io/nvidia/pytorch:24.08-py3

# Install system dependencies for audio
RUN apt-get update && apt-get install -y \
    portaudio19-dev \
    python3-pyaudio \
    libasound2-dev \
    alsa-utils \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt /tmp/requirements.txt

# Install Python dependencies globally (not in /app)
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy application code
COPY . .

# Create socket directory
RUN mkdir -p /tmp/reachy_sockets

# Create entrypoint script to install dependencies if needed
RUN echo '#!/bin/bash\n\
if [ -f /app/requirements.txt ]; then\n\
    pip install --no-cache-dir -r /app/requirements.txt > /dev/null 2>&1 || true\n\
fi\n\
exec "$@"' > /entrypoint.sh && chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

# Default command
CMD ["python3", "hearing_event_emitter.py"]
