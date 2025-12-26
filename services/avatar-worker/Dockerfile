FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

# Install Python 3.10
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    git \
    wget \
    unzip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install gltfpack
RUN wget https://github.com/zeux/meshoptimizer/releases/download/v0.20/gltfpack-0.20-linux.zip \
    && unzip gltfpack-0.20-linux.zip \
    && mv gltfpack /usr/local/bin/ \
    && chmod +x /usr/local/bin/gltfpack \
    && rm gltfpack-0.20-linux.zip

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Create models directory (user must mount SMPL-X models)
RUN mkdir -p /app/models/smplx

# Set environment variables
ENV PYTHONUNBUFFERED=1

CMD ["python3", "src/worker.py"]
