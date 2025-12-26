"""
GLB Optimizer - Compress and optimize GLB files using gltfpack

This module handles optimizing GLB files to reduce file size and triangle count
while maintaining visual quality.
"""

import subprocess
import logging
import os

logger = logging.getLogger(__name__)


class GLBOptimizer:
    """Optimize GLB files using gltfpack"""
    
    def __init__(self, gltfpack_path: str = "gltfpack", require_gltfpack: bool = False):
        """
        Initialize GLB optimizer
        
        Args:
            gltfpack_path: Path to gltfpack binary
            require_gltfpack: If true, fail the job when gltfpack is missing or errors
        """
        self.gltfpack_path = gltfpack_path
        self.require_gltfpack = require_gltfpack
        logger.info(f"Initializing GLB optimizer with gltfpack: {gltfpack_path}")

        if any(ord(ch) < 32 for ch in gltfpack_path):
            logger.warning(
                "GLTFPACK_PATH contains control characters (raw=%r). "
                "On Windows this commonly happens when a quoted .env value decodes backslashes "
                "(e.g. \"C:\\\\Users\\\\me\\\\tools\\\\gltfpack.exe\" -> \"C:\\\\Users\\\\me\\t...\" tab). "
                "Use forward slashes (C:/Users/me/tools/gltfpack.exe) or double-backslashes.",
                gltfpack_path,
            )
        
    def optimize(self, input_path: str, output_path: str, target_triangles: int = 10000) -> str:
        """
        Optimize GLB file
        
        Args:
            input_path: Path to input GLB file
            output_path: Path to save optimized GLB file
            target_triangles: Target triangle count (default: 10000)
            
        Returns:
            Path to optimized GLB file
        """
        logger.info(f"Optimizing GLB: {input_path} → {output_path}")
        logger.info(f"Target triangles: {target_triangles}")
        
        try:
            # Run gltfpack
            cmd = [
                self.gltfpack_path,
                "-i", input_path,
                "-o", output_path,
                "-si", str(target_triangles / 1000),  # Simplification ratio
                "-cc",  # Compress colors
                "-tc",  # Compress textures
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            logger.info(f"gltfpack output: {result.stdout}")
            
            # Check output file size
            if os.path.exists(output_path):
                size_mb = os.path.getsize(output_path) / (1024 * 1024)
                logger.info(f"Optimized GLB size: {size_mb:.2f} MB")
                
                if size_mb > 2.0:
                    logger.warning(f"GLB file size ({size_mb:.2f} MB) exceeds 2MB target")
            
            return output_path
            
        except subprocess.CalledProcessError as e:
            logger.error(f"gltfpack failed: {e.stderr}")
            if self.require_gltfpack:
                raise RuntimeError(f"gltfpack failed: {e.stderr}") from e
            logger.warning("Using unoptimized GLB file")
            return input_path
        except FileNotFoundError:
            logger.error(f"gltfpack not found at: {self.gltfpack_path} (raw={self.gltfpack_path!r})")
            if self.require_gltfpack:
                raise RuntimeError(f"gltfpack not found: {self.gltfpack_path}") from None
            logger.warning("Using unoptimized GLB file")
            return input_path
