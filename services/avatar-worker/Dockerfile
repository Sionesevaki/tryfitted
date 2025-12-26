FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

# External repos pinned for reproducible builds.
# These repos contain code only; large model weights are still mounted via volumes at runtime.
ARG PIXIE_GIT_URL=https://github.com/yfeng95/PIXIE.git
ARG PIXIE_GIT_REF=5c8879b828fc78e69b8d457029b27e825eae0d1c
ARG SMPL_ANTHRO_GIT_URL=https://github.com/DavidBoja/SMPL-Anthropometry.git
ARG SMPL_ANTHRO_GIT_REF=d8f43bca7a2ae6263f43ebb0efe74136e37e25eb
ARG SAM3DBODY_GIT_URL=https://github.com/facebookresearch/sam-3d-body.git
ARG SAM3DBODY_GIT_REF=c259bfc38500b1ce9e7048e1a4592e13b84108fe
ARG SAM2_GIT_URL=https://github.com/facebookresearch/sam2.git
ARG SAM2_GIT_REF=2b90b9f5ceec907a1c18123530e92e794ad901a4

# Ensure Docker installs CUDA-enabled PyTorch (otherwise `pip install torch` often pulls CPU-only wheels).
ENV PIP_INDEX_URL=https://download.pytorch.org/whl/cu118
ENV PIP_EXTRA_INDEX_URL=https://pypi.org/simple

# Install Python 3.10
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    git \
    wget \
    unzip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install gltfpack (meshoptimizer). Asset names vary by release; try common variants.
ARG GLTFPACK_VERSION=0.20
RUN set -eux; \
    base="https://github.com/zeux/meshoptimizer/releases/download/v${GLTFPACK_VERSION}"; \
    for asset in "gltfpack-${GLTFPACK_VERSION}-linux.zip" "gltfpack-linux.zip" "gltfpack-linux-x64.zip"; do \
      if wget -q -O /tmp/gltfpack.zip "${base}/${asset}"; then \
        echo "Downloaded ${asset}"; \
        break; \
      fi; \
    done; \
    test -s /tmp/gltfpack.zip; \
    unzip /tmp/gltfpack.zip; \
    mv gltfpack /usr/local/bin/; \
    chmod +x /usr/local/bin/gltfpack; \
    rm -f /tmp/gltfpack.zip

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

# Fetch optional fit-accuracy dependencies (code only): sam-3d-body + sam2.
RUN set -eux; \
    mkdir -p /app/vendors; \
    if [ ! -f /app/vendors/sam-3d-body/sam_3d_body/__init__.py ]; then \
      rm -rf /app/vendors/sam-3d-body; \
      git init /tmp/sam3db; \
      git -C /tmp/sam3db remote add origin "$SAM3DBODY_GIT_URL"; \
      git -C /tmp/sam3db fetch --depth 1 origin "$SAM3DBODY_GIT_REF"; \
      git -C /tmp/sam3db checkout --detach FETCH_HEAD; \
      rm -rf /tmp/sam3db/.git; \
      mv /tmp/sam3db /app/vendors/sam-3d-body; \
    fi; \
    if [ ! -f /app/vendors/sam2/sam2/__init__.py ]; then \
      rm -rf /app/vendors/sam2; \
      git init /tmp/sam2; \
      git -C /tmp/sam2 remote add origin "$SAM2_GIT_URL"; \
      git -C /tmp/sam2 fetch --depth 1 origin "$SAM2_GIT_REF"; \
      git -C /tmp/sam2 checkout --detach FETCH_HEAD; \
      rm -rf /tmp/sam2/.git; \
      mv /tmp/sam2 /app/vendors/sam2; \
    fi

# Entry point copies large weights from /app/models into the locations expected by code, then starts the worker.
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create models directory (user must mount SMPL-X models)
RUN mkdir -p /app/models/smplx

# Set environment variables
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["/entrypoint.sh"]
