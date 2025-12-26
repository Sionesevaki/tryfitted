FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

# External repos pinned for reproducible builds.
# These repos contain code only; large model weights are still mounted via volumes at runtime.
ARG PIXIE_GIT_URL=https://github.com/yfeng95/PIXIE.git
ARG PIXIE_GIT_REF=5c8879b828fc78e69b8d457029b27e825eae0d1c
ARG SMPL_ANTHRO_GIT_URL=https://github.com/DavidBoja/SMPL-Anthropometry.git
ARG SMPL_ANTHRO_GIT_REF=d8f43bca7a2ae6263f43ebb0efe74136e37e25eb

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

# Fetch external source dependencies (code only).
RUN set -eux; \
    mkdir -p /app/src/pipeline; \
    if [ ! -d /app/src/pipeline/PIXIE/pixielib ]; then \
      rm -rf /app/src/pipeline/PIXIE; \
      git init /tmp/pixie; \
      git -C /tmp/pixie remote add origin "$PIXIE_GIT_URL"; \
      git -C /tmp/pixie fetch --depth 1 origin "$PIXIE_GIT_REF"; \
      git -C /tmp/pixie checkout --detach FETCH_HEAD; \
      rm -rf /tmp/pixie/.git; \
      mv /tmp/pixie /app/src/pipeline/PIXIE; \
    fi; \
    if [ ! -f /app/src/pipeline/SMPL-Anthropometry/measure.py ]; then \
      rm -rf /app/src/pipeline/SMPL-Anthropometry; \
      git init /tmp/smpl_anthro; \
      git -C /tmp/smpl_anthro remote add origin "$SMPL_ANTHRO_GIT_URL"; \
      git -C /tmp/smpl_anthro fetch --depth 1 origin "$SMPL_ANTHRO_GIT_REF"; \
      git -C /tmp/smpl_anthro checkout --detach FETCH_HEAD; \
      rm -rf /tmp/smpl_anthro/.git; \
      mv /tmp/smpl_anthro /app/src/pipeline/SMPL-Anthropometry; \
    fi

# Create models directory (user must mount SMPL-X models)
RUN mkdir -p /app/models/smplx

# Set environment variables
ENV PYTHONUNBUFFERED=1

CMD ["python3", "src/worker.py"]
