"""
Measurements Extractor - Integration with SMPL-Anthropometry

This module handles extracting body measurements from SMPL-X models using
the SMPL-Anthropometry library.
"""

import sys
import os
import logging
import numpy as np
from typing import Dict, Any
import torch

# Add SMPL-Anthropometry to path
SMPL_ANTHRO_PATH = os.path.join(os.path.dirname(__file__), "SMPL-Anthropometry")
sys.path.insert(0, SMPL_ANTHRO_PATH)

logger = logging.getLogger(__name__)


class MeasurementExtractor:
    """Extract body measurements from SMPL-X models"""
    
    def __init__(self, smplx_model_dir: str):
        """
        Initialize measurement extractor
        
        Args:
            smplx_model_dir: Path to SMPL-X model directory
        """
        self.smplx_model_dir = smplx_model_dir
        self.measurer = None
        
        logger.info(f"Initializing measurement extractor with model_dir: {smplx_model_dir}")
        
        try:
            self._load_measurer()
        except Exception as e:
            logger.error(f"Failed to load SMPL-Anthropometry: {e}")
            logger.warning("Measurement extractor loading failed - using placeholder mode")
    
    def _load_measurer(self):
        """Load SMPL-Anthropometry measurement system"""
        try:
            # Configure SMPL-Anthropometry to find (1) its own data assets and (2) your SMPL-X model files.
            # - data assets (segmentation json, etc) live under the vendored repo `SMPL_ANTHRO_PATH/data`
            # - SMPL-X model files live under `self.smplx_model_dir` (folder containing SMPLX_*.*)
            data_root = os.path.join(SMPL_ANTHRO_PATH, "data")
            body_model_root = os.path.abspath(os.path.join(self.smplx_model_dir, os.pardir))

            # Important: set these BEFORE importing `measure.py` (it reads env at import time).
            os.environ["SMPL_ANTHRO_DATA_ROOT"] = data_root
            os.environ["SMPL_ANTHRO_BODY_MODEL_ROOT"] = body_model_root

            # Prefer user override; otherwise auto-detect from available files.
            if "SMPL_ANTHRO_MODEL_EXT" not in os.environ:
                has_pkl = any(name.lower().endswith(".pkl") for name in os.listdir(self.smplx_model_dir)) if os.path.isdir(self.smplx_model_dir) else False
                has_npz = any(name.lower().endswith(".npz") for name in os.listdir(self.smplx_model_dir)) if os.path.isdir(self.smplx_model_dir) else False
                os.environ["SMPL_ANTHRO_MODEL_EXT"] = "pkl" if has_pkl else "npz" if has_npz else "pkl"

            from measure import MeasureBody

            logger.info("Loading SMPL-Anthropometry measurement system...")
            logger.info(f"SMPL-Anthro data root: {data_root}")
            logger.info(f"SMPL-Anthro body model root: {body_model_root}")
            logger.info(f"SMPL-Anthro model ext: {os.environ.get('SMPL_ANTHRO_MODEL_EXT')}")
            self.measurer = MeasureBody("smplx")
            
            logger.info("SMPL-Anthropometry loaded successfully")
            
        except ImportError as e:
            logger.error(f"Failed to import SMPL-Anthropometry modules: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load measurement system: {e}")
            raise
    
    def extract_measurements(self, smplx_params: Dict[str, Any]) -> Dict[str, float]:
        """
        Extract body measurements from SMPL-X parameters
        
        Args:
            smplx_params: SMPL-X parameters (betas, pose, etc.)
            
        Returns:
            Dictionary of measurements in centimeters
        """
        logger.info("Extracting measurements from SMPL-X parameters")
        
        if self.measurer is None:
            logger.warning("Measurer not loaded - using placeholder measurements")
            return self._generate_placeholder_measurements()
        
        try:
            used_mesh = False

            mesh_payload = smplx_params.get("mesh")
            if isinstance(mesh_payload, dict) and "vertices" in mesh_payload:
                verts = np.asarray(mesh_payload["vertices"])
                if verts.ndim == 2 and verts.shape[1] == 3:
                    try:
                        self.measurer.from_verts(torch.tensor(verts, dtype=torch.float32))
                        used_mesh = True
                    except Exception as e:
                        logger.warning(f"Failed to measure from verts; falling back to betas-based model: {e}")

            if not used_mesh:
                betas_raw = smplx_params.get("betas", np.zeros(10))
                betas = torch.tensor(betas_raw, dtype=torch.float32).reshape(1, -1)[:, :10]
                self.measurer.from_body_model(gender="neutral", shape=betas)

            # Compute measurements (SMPL-Anthropometry does not populate `measurements` until `measure()` is called).
            required = [
                "height",
                "shoulder breadth",
                "shoulder to crotch height",
                "arm right length",
                "inside leg height",
                "neck circumference",
                "chest circumference",
                "waist circumference",
                "hip circumference",
                "wrist right circumference",
                "bicep right circumference",
                "forearm right circumference",
                "thigh left circumference",
                "calf left circumference",
                "ankle left circumference",
            ]

            self.measurer.measurements = {}
            self.measurer.measure(required)
            measurements_dict = self.measurer.measurements

            shoulder_breadth = measurements_dict.get("shoulder breadth", 0.0)

            # Convert to our schema (SMPL-Anthropometry returns cm)
            measurements = {
                "chestCm": float(measurements_dict.get("chest circumference", 0.0)),
                "waistCm": float(measurements_dict.get("waist circumference", 0.0)),
                "hipCm": float(measurements_dict.get("hip circumference", 0.0)),
                "shoulderCm": float(shoulder_breadth),
                "sleeveCm": float(measurements_dict.get("arm right length", 0.0)),
                "lengthCm": float(measurements_dict.get("shoulder to crotch height", 0.0)),
                "neckCm": float(measurements_dict.get("neck circumference", 0.0)),
                "bicepCm": float(measurements_dict.get("bicep right circumference", 0.0)),
                "forearmCm": float(measurements_dict.get("forearm right circumference", 0.0)),
                "wristCm": float(measurements_dict.get("wrist right circumference", 0.0)),
                "thighCm": float(measurements_dict.get("thigh left circumference", 0.0)),
                "calfCm": float(measurements_dict.get("calf left circumference", 0.0)),
                "ankleCm": float(measurements_dict.get("ankle left circumference", 0.0)),
                "insideLegCm": float(measurements_dict.get("inside leg height", 0.0)),
                "shoulderBreadthCm": float(shoulder_breadth),
                "heightCm": float(measurements_dict.get("height", 0.0)),
            }
            
            logger.info(f"Extracted {len(measurements)} measurements")
            return measurements
            
        except Exception as e:
            logger.error(f"Measurement extraction failed: {e}")
            logger.warning("Falling back to placeholder measurements")
            return self._generate_placeholder_measurements()
    
    def _generate_placeholder_measurements(self) -> Dict[str, float]:
        """Generate placeholder measurements for testing"""
        return {
            "chestCm": 98.5,
            "waistCm": 82.3,
            "hipCm": 95.7,
            "shoulderCm": 44.2,
            "sleeveCm": 61.8,
            "lengthCm": 68.4,
            "neckCm": 38.1,
            "bicepCm": 32.5,
            "forearmCm": 27.3,
            "wristCm": 17.2,
            "thighCm": 56.8,
            "calfCm": 37.4,
            "ankleCm": 23.6,
            "insideLegCm": 78.9,
            "shoulderBreadthCm": 42.1,
            "heightCm": 175.0,
        }
    
    def generate_quality_report(self, measurements: Dict[str, float], confidence: float, placeholder: bool = False) -> Dict[str, Any]:
        """
        Generate quality report for measurements
        
        Args:
            measurements: Extracted measurements
            confidence: PIXIE confidence score
            
        Returns:
            Quality report with confidence and warnings
        """
        warnings = []
        
        if placeholder:
            warnings.append("Avatar pipeline produced placeholder output (PIXIE/SMPL-X or measurements unavailable)")

        # Check for missing measurements
        expected_keys = ["chestCm", "waistCm", "hipCm", "shoulderCm", "sleeveCm", "lengthCm"]
        missing = [key for key in expected_keys if key not in measurements or measurements[key] is None or measurements[key] == 0]
        if missing:
            warnings.append(f"Missing or zero measurements: {', '.join(missing)}")
        
        # Check for unrealistic measurements
        if measurements.get("heightCm", 0) < 140 or measurements.get("heightCm", 0) > 220:
            warnings.append("Height measurement seems unrealistic")
        
        if measurements.get("chestCm", 0) < 70 or measurements.get("chestCm", 0) > 150:
            warnings.append("Chest measurement seems unrealistic")
        
        # Determine overall confidence
        if confidence >= 0.8 and not warnings:
            quality = "high"
        elif confidence >= 0.6:
            quality = "medium"
        else:
            quality = "low"
            warnings.append("Low PIXIE confidence score")
        
        report: Dict[str, Any] = {"confidence": quality}
        if warnings:
            report["warnings"] = warnings
        return report
