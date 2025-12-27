FROM pytorch/pytorch:2.1.2-cuda11.8-cudnn8-runtime AS builder

# Prevent interactive apt prompts (e.g., tzdata).
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

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

# Keep pip output quieter in CI.
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps for building native tools (gltfpack) and fetching pinned repos.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    git \
    wget \
    unzip \
    ca-certificates \
    build-essential \
    cmake \
    && ln -snf "/usr/share/zoneinfo/$TZ" /etc/localtime \
    && echo "$TZ" > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# Install gltfpack (meshoptimizer). This is required for production optimization.
ARG GLTFPACK_VERSION=0.20
ARG MESHOPTIMIZER_GIT_URL=https://github.com/zeux/meshoptimizer.git
ARG MESHOPTIMIZER_GIT_REF=v0.20
RUN set -eux; \
    install_gltfpack_from_base() { \
      base="$1"; \
      for asset in \
        "gltfpack-${GLTFPACK_VERSION}-linux.zip" \
        "gltfpack-${GLTFPACK_VERSION}-linux-x64.zip" \
        "gltfpack-linux.zip" \
        "gltfpack-linux-x64.zip" \
        "gltfpack-linux.tar.gz" \
        "gltfpack-linux-x64.tar.gz" \
        "gltfpack-linux" \
        "gltfpack" \
      ; do \
        if wget -q -O /tmp/gltfpack.bin "${base}/${asset}"; then \
          if unzip -q -t /tmp/gltfpack.bin >/dev/null 2>&1; then \
            mv /tmp/gltfpack.bin /tmp/gltfpack.zip; \
            unzip -q /tmp/gltfpack.zip -d /tmp/gltfpack_unzip; \
            if [ -f /tmp/gltfpack_unzip/gltfpack ]; then \
              mv /tmp/gltfpack_unzip/gltfpack /usr/local/bin/gltfpack; \
            elif [ -f /tmp/gltfpack_unzip/bin/gltfpack ]; then \
              mv /tmp/gltfpack_unzip/bin/gltfpack /usr/local/bin/gltfpack; \
            else \
              rm -rf /tmp/gltfpack_unzip /tmp/gltfpack.zip; \
              return 1; \
            fi; \
            rm -rf /tmp/gltfpack_unzip /tmp/gltfpack.zip; \
          else \
            mv /tmp/gltfpack.bin /usr/local/bin/gltfpack; \
          fi; \
          chmod +x /usr/local/bin/gltfpack; \
          return 0; \
        fi; \
      done; \
      rm -f /tmp/gltfpack.bin /tmp/gltfpack.zip || true; \
      return 1; \
    }; \
    build_gltfpack_from_source() { \
      rm -rf /tmp/meshoptimizer; \
      git init /tmp/meshoptimizer; \
      git -C /tmp/meshoptimizer remote add origin "$MESHOPTIMIZER_GIT_URL"; \
      git -C /tmp/meshoptimizer fetch --depth 1 origin "$MESHOPTIMIZER_GIT_REF"; \
      git -C /tmp/meshoptimizer checkout --detach FETCH_HEAD; \
      cmake -S /tmp/meshoptimizer -B /tmp/meshoptimizer/build -DCMAKE_BUILD_TYPE=Release -DMESHOPT_BUILD_TOOLS=ON -DMESHOPT_BUILD_GLTFPACK=ON; \
      cmake --build /tmp/meshoptimizer/build --target gltfpack -j"$(nproc)"; \
      if [ -x /tmp/meshoptimizer/build/gltfpack ]; then \
        mv /tmp/meshoptimizer/build/gltfpack /usr/local/bin/gltfpack; \
      elif [ -x /tmp/meshoptimizer/build/bin/gltfpack ]; then \
        mv /tmp/meshoptimizer/build/bin/gltfpack /usr/local/bin/gltfpack; \
      else \
        echo "ERROR: gltfpack binary not found after source build"; \
        find /tmp/meshoptimizer/build -maxdepth 3 -type f -name gltfpack -print; \
        return 1; \
      fi; \
      chmod +x /usr/local/bin/gltfpack; \
      rm -rf /tmp/meshoptimizer; \
    }; \
    if command -v gltfpack >/dev/null 2>&1; then \
      echo "gltfpack already installed"; \
    elif install_gltfpack_from_base "https://github.com/zeux/meshoptimizer/releases/download/v${GLTFPACK_VERSION}"; then \
      echo "Installed gltfpack (tag v${GLTFPACK_VERSION})"; \
    elif install_gltfpack_from_base "https://github.com/zeux/meshoptimizer/releases/latest/download"; then \
      echo "Installed gltfpack (latest)"; \
    else \
      echo "gltfpack release download failed; building from source..."; \
      build_gltfpack_from_source; \
      echo "Installed gltfpack (built from source: ${MESHOPTIMIZER_GIT_REF})"; \
    fi

WORKDIR /app

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

FROM pytorch/pytorch:2.1.2-cuda11.8-cudnn8-runtime AS runtime

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PYTHONUNBUFFERED=1

# Runtime deps only (no build toolchain).
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    ca-certificates \
    && ln -snf "/usr/share/zoneinfo/$TZ" /etc/localtime \
    && echo "$TZ" > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy gltfpack from builder (and any other helper binaries we installed there).
COPY --from=builder /usr/local/bin/gltfpack /usr/local/bin/gltfpack

# App + vendored repos cloned during build
COPY --from=builder /app/ /app/

# Entrypoint
COPY --from=builder /entrypoint.sh /entrypoint.sh

# Install Python deps (excluding torch/torchvision — already in base image).
COPY requirements.docker.txt /app/requirements.docker.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r /app/requirements.docker.txt

# Ensure `python3` exists (some images provide `python` only).
RUN if ! command -v python3 >/dev/null 2>&1 && command -v python >/dev/null 2>&1; then \
      ln -s "$(command -v python)" /usr/local/bin/python3; \
    fi

ENTRYPOINT ["/entrypoint.sh"]
