"""
PIXIE Runner - Integration with PIXIE for SMPL-X body reconstruction

This module handles loading the PIXIE model and processing images to generate
SMPL-X parameters and meshes.
"""

import sys
import os
import numpy as np
import torch
import trimesh
from typing import Dict, Any
import logging

# Add PIXIE to path
PIXIE_PATH = os.path.join(os.path.dirname(__file__), "PIXIE")
sys.path.insert(0, PIXIE_PATH)

logger = logging.getLogger(__name__)


class PIXIERunner:
    """PIXIE model runner for SMPL-X body reconstruction"""
    
    def __init__(self, model_dir: str, smplx_model_dir: str):
        """
        Initialize PIXIE model
        
        Args:
            model_dir: Path to PIXIE model directory
            smplx_model_dir: Path to SMPL-X model directory
        """
        self.model_dir = model_dir
        self.smplx_model_dir = smplx_model_dir
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = None
        self.smplx_model = None
        
        logger.info(f"Initializing PIXIE runner with model_dir: {model_dir}")
        logger.info(f"Using device: {self.device}")
        
        try:
            self._load_models()
        except Exception as e:
            logger.error(f"Failed to load PIXIE models: {e}")
            logger.warning("PIXIE model loading failed - using placeholder mode")

    def _encode_decode(self, image_path: str):
        from pixielib.datasets.body_datasets import TestData
        from pixielib.utils import util

        testdata = TestData(image_path, iscrop=False, body_detector="none", device=str(self.device))
        batch = testdata[0]
        util.move_dict_to_device(batch, str(self.device))
        batch["image"] = batch["image"].unsqueeze(0)
        batch["image_hd"] = batch["image_hd"].unsqueeze(0)

        data = {"body": batch}

        with torch.no_grad():
            param_dict = self.model.encode(data, threthold=True, keep_local=True, copy_and_paste=False)
            codedict = param_dict["body"]
            opdict = self.model.decode(codedict, param_type="body")

        return codedict, opdict

    def _decode_tpose_vertices(self, codedict: Dict[str, Any]) -> torch.Tensor:
        return self.model.decode_Tpose(codedict)

    def _decode_apose_vertices(self, codedict: Dict[str, Any], arm_down_degrees: float) -> torch.Tensor:
        """
        Decode an "A-pose" mesh (arms slightly lowered from T-pose) to avoid arms intersecting the torso
        and to look more natural for try-on.
        """
        shape = codedict["shape"]
        exp = codedict.get("exp", None)
        jaw_pose = codedict.get("jaw_pose", None)

        batch_size = shape.shape[0]
        body_pose = self.model.smplx.body_pose.unsqueeze(0).expand(batch_size, -1, -1, -1).clone()

        theta = float(arm_down_degrees) * np.pi / 180.0
        c = float(np.cos(theta))
        s = float(np.sin(theta))

        rot_z = torch.tensor([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]], dtype=body_pose.dtype, device=body_pose.device)

        # SMPL-X: body_pose excludes the pelvis (global_pose). In PIXIE's SMPLX_names list, shoulders are:
        # left_shoulder index=16, right_shoulder index=17 (0-based), so body_pose indices are 15 and 16.
        left_shoulder_idx = 15
        right_shoulder_idx = 16

        body_pose[:, left_shoulder_idx] = rot_z
        body_pose[:, right_shoulder_idx] = rot_z.transpose(0, 1)  # inverse rotation

        verts, _, _ = self.model.smplx(
            shape_params=shape,
            expression_params=exp,
            jaw_pose=jaw_pose,
            body_pose=body_pose,
        )
        return verts

    def _scale_and_ground_vertices(self, verts: torch.Tensor, height_cm: float | None) -> torch.Tensor:
        """
        Scale vertices so the resulting mesh height matches the user-provided height (cm),
        then translate so the lowest vertex rests at y=0 (helps consistent viewing/try-on).
        """
        if height_cm is None:
            return verts

        try:
            target_m = float(height_cm) / 100.0
        except Exception:
            return verts

        if not (0.5 <= target_m <= 2.5):
            return verts

        verts2 = verts.clone()
        y = verts2[:, :, 1]
        current_h = (y.max(dim=1).values - y.min(dim=1).values).clamp(min=1e-6)
        scale = (target_m / current_h).clamp(min=0.5, max=2.0).view(-1, 1, 1)
        verts2 = verts2 * scale

        y2 = verts2[:, :, 1]
        min_y = y2.min(dim=1).values.view(-1, 1, 1)
        verts2[:, :, 1:2] = verts2[:, :, 1:2] - min_y
        return verts2

    def build_meshes_from_betas(self, betas10: np.ndarray, height_cm: float) -> Dict[str, Any]:
        """
        Build the canonical (T-pose) mesh for measurements and the display mesh for rendering,
        using only SMPL-X shape parameters.
        """
        if self.model is None:
            return self._generate_placeholder_params()

        shape = torch.tensor(np.asarray(betas10, dtype=np.float32).reshape(1, -1)[:, :10], device=self.device)
        # PIXIE SMPLX expects n_shape, but will accept fewer and pad internally via shapedirs slicing.
        # Provide zeros for expression/jaw.
        exp = torch.zeros((1, self.model.cfg.model.n_exp), device=self.device, dtype=torch.float32) if hasattr(self.model, "cfg") else None
        jaw = torch.eye(3, device=self.device, dtype=torch.float32).view(1, 1, 3, 3)

        # T-pose / neutral body pose
        tpose_verts, _, _ = self.model.smplx(shape_params=shape, expression_params=exp, jaw_pose=jaw)

        # Display pose
        pose = os.getenv("AVATAR_DISPLAY_POSE", "apose").lower()
        if pose == "tpose":
            display_verts = tpose_verts
        elif pose == "apose":
            display_verts = self._decode_apose_vertices({"shape": shape, "exp": exp, "jaw_pose": jaw}, float(os.getenv("AVATAR_APOSE_ARM_DOWN_DEG", "25")))
        else:
            # If asked for pixie pose but we only have betas, fall back to apose.
            display_verts = self._decode_apose_vertices({"shape": shape, "exp": exp, "jaw_pose": jaw}, float(os.getenv("AVATAR_APOSE_ARM_DOWN_DEG", "25")))

        tpose_verts = self._scale_and_ground_vertices(tpose_verts, height_cm)
        display_verts = self._scale_and_ground_vertices(display_verts, height_cm)

        faces = self.model.smplx.faces_tensor.detach().cpu().numpy()
        return {
            "mesh": {"vertices": tpose_verts.detach().cpu().numpy()[0], "faces": faces},
            "displayMesh": {"vertices": display_verts.detach().cpu().numpy()[0], "faces": faces},
        }

    def _select_display_vertices(self, codedict: Dict[str, Any], posed_vertices: torch.Tensor | None) -> torch.Tensor:
        pose = os.getenv("AVATAR_DISPLAY_POSE", "apose").lower()
        if pose == "pixie" and posed_vertices is not None:
            return posed_vertices
        if pose == "tpose":
            return self._decode_tpose_vertices(codedict)
        if pose == "apose":
            arm_down = float(os.getenv("AVATAR_APOSE_ARM_DOWN_DEG", "25"))
            return self._decode_apose_vertices(codedict, arm_down_degrees=arm_down)
        logger.warning(f"Unknown AVATAR_DISPLAY_POSE={pose!r}; falling back to apose")
        return self._decode_apose_vertices(codedict, arm_down_degrees=25)

    def process_images(self, front_image_path: str, side_image_path: str | None, height_cm: float) -> Dict[str, Any]:
        """
        Process front + (optional) side images to generate SMPL-X parameters.

        Current strategy (simple + robust): run PIXIE on each image and fuse the shape (betas) by averaging.
        """
        logger.info(f"Processing images (front={front_image_path}, side={side_image_path}), height: {height_cm}cm")

        if self.model is None:
            logger.warning("PIXIE model not loaded - using placeholder")
            return self._generate_placeholder_params()

        side_ok = bool(side_image_path) and os.path.exists(side_image_path) and os.path.getsize(side_image_path) > 0
        if not side_ok:
            return self.process_image(front_image_path, height_cm)

        try:
            codedict_front, _ = self._encode_decode(front_image_path)
            codedict_side, _ = self._encode_decode(side_image_path)  # type: ignore[arg-type]

            shape_front = codedict_front.get("shape")
            shape_side = codedict_side.get("shape")
            if shape_front is None or shape_side is None:
                logger.warning("PIXIE did not return shape for one of the images; falling back to front only")
                return self.process_image(front_image_path, height_cm)

            # Fuse betas (shape) by averaging; keep pose/expression from front.
            fused_shape = (shape_front + shape_side) / 2.0

            fused_codedict: Dict[str, Any] = {}
            for key, value in codedict_front.items():
                if torch.is_tensor(value):
                    fused_codedict[key] = value.clone()
                else:
                    fused_codedict[key] = value
            fused_codedict["shape"] = fused_shape

            fused_opdict = self.model.decode(fused_codedict, param_type="body")

            posed_verts_t = fused_opdict["vertices"]
            tpose_verts_t = self._decode_tpose_vertices(fused_codedict)
            display_verts_t = self._select_display_vertices(fused_codedict, posed_vertices=posed_verts_t)

            tpose_verts_t = self._scale_and_ground_vertices(tpose_verts_t, height_cm)
            display_verts_t = self._scale_and_ground_vertices(display_verts_t, height_cm)

            verts = tpose_verts_t.detach().cpu().numpy()[0]
            display_verts = display_verts_t.detach().cpu().numpy()[0]
            faces = self.model.smplx.faces_tensor.detach().cpu().numpy()

            betas_np = fused_shape.detach().cpu().numpy()[0]

            return {
                "betas": betas_np[:10],
                "confidence": 0.9,
                "placeholder": False,
                "mesh": {"vertices": verts, "faces": faces},
                "displayMesh": {"vertices": display_verts, "faces": faces},
                "heightCm": float(height_cm),
                "sources": {"front": True, "side": True},
            }
        except Exception as e:
            logger.error(f"PIXIE multi-view processing failed: {e}", exc_info=True)
            logger.warning("Falling back to front-only PIXIE output")
            return self.process_image(front_image_path, height_cm)
    
    def _load_models(self):
        """Load PIXIE and SMPL-X models"""
        try:
            # Import PIXIE modules
            from pixielib.pixie import PIXIE
            from pixielib.utils.config import cfg as pixie_cfg
            
            # Load PIXIE model
            logger.info("Loading PIXIE model...")
            pixie_cfg.device = "cuda" if self.device.type == "cuda" else "cpu"
            pixie_cfg.pretrained_modelpath = os.path.join(PIXIE_PATH, "data", "pixie_model.tar")

            # Avoid requiring the optional FLAME albedo file (FLAME_albedo_from_BFM.npz) unless explicitly enabled.
            pixie_cfg.model.use_tex = os.getenv("PIXIE_USE_TEX", "false").lower() == "true"

            if not os.path.exists(pixie_cfg.pretrained_modelpath):
                raise FileNotFoundError(
                    f"Missing PIXIE weights at {pixie_cfg.pretrained_modelpath}. "
                    "PIXIE/data in this repo is incomplete; follow PIXIE instructions to download pixie_model.tar and required assets."
                )

            self.model = PIXIE(config=pixie_cfg, device=str(self.device))
            self.smplx_model = None
            
            logger.info("PIXIE and SMPL-X models loaded successfully")
            
        except ImportError as e:
            logger.error(f"Failed to import PIXIE modules: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load models: {e}")
            raise
    
    def process_image(self, image_path: str, height_cm: float) -> Dict[str, Any]:
        """
        Process image to generate SMPL-X parameters
        
        Args:
            image_path: Path to input image
            height_cm: Person's height in centimeters
            
        Returns:
            Dictionary containing SMPL-X parameters and metadata
        """
        logger.info(f"Processing image: {image_path}, height: {height_cm}cm")
        
        if self.model is None:
            logger.warning("PIXIE model not loaded - using placeholder")
            return self._generate_placeholder_params()
        
        try:
            codedict, opdict = self._encode_decode(image_path)

            posed_verts_t = opdict["vertices"]
            tpose_verts_t = self._decode_tpose_vertices(codedict)
            display_verts_t = self._select_display_vertices(codedict, posed_vertices=posed_verts_t)

            tpose_verts_t = self._scale_and_ground_vertices(tpose_verts_t, height_cm)
            display_verts_t = self._scale_and_ground_vertices(display_verts_t, height_cm)

            verts = tpose_verts_t.detach().cpu().numpy()[0]
            display_verts = display_verts_t.detach().cpu().numpy()[0]
            faces = self.model.smplx.faces_tensor.detach().cpu().numpy()

            betas = codedict.get("shape")
            betas_np = betas.detach().cpu().numpy()[0] if betas is not None else np.zeros(10)

            return {
                "betas": betas_np[:10],
                "confidence": 0.85,
                "placeholder": False,
                "mesh": {"vertices": verts, "faces": faces},
                "displayMesh": {"vertices": display_verts, "faces": faces},
                "heightCm": float(height_cm),
            }
        except Exception as e:
            logger.error(f"PIXIE processing failed: {e}", exc_info=True)
            logger.warning("Falling back to placeholder parameters")
            return self._generate_placeholder_params()
    
    def _generate_placeholder_params(self) -> Dict[str, Any]:
        """Generate placeholder SMPL-X parameters for testing"""
        return {
            "betas": np.zeros(10),
            "body_pose": np.zeros(63),
            "global_orient": np.zeros(3),
            "transl": np.zeros(3),
            "left_hand_pose": np.zeros(15),
            "right_hand_pose": np.zeros(15),
            "jaw_pose": np.zeros(3),
            "expression": np.zeros(10),
            "confidence": 0.5,
            "placeholder": True,
        }
    
    def export_mesh(self, smplx_params: Dict[str, Any], output_path: str) -> str:
        """
        Export SMPL-X mesh as GLB file
        
        Args:
            smplx_params: SMPL-X parameters from process_image
            output_path: Path to save GLB file
            
        Returns:
            Path to exported GLB file
        """
        logger.info(f"Exporting mesh to: {output_path}")
        
        mesh_payload = smplx_params.get("displayMesh") or smplx_params.get("mesh")
        if isinstance(mesh_payload, dict) and "vertices" in mesh_payload and "faces" in mesh_payload:
            vertices = np.asarray(mesh_payload["vertices"])
            faces = np.asarray(mesh_payload["faces"])
            mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
            mesh.export(output_path)
            return output_path

        if self.smplx_model is None:
            logger.warning("SMPL-X model not loaded - creating placeholder mesh")
            return self._export_placeholder_mesh(output_path)
        
        try:
            # Convert parameters to tensors
            betas = torch.tensor(smplx_params['betas'], dtype=torch.float32).unsqueeze(0).to(self.device)
            body_pose = torch.tensor(smplx_params['body_pose'], dtype=torch.float32).unsqueeze(0).to(self.device)
            global_orient = torch.tensor(smplx_params['global_orient'], dtype=torch.float32).unsqueeze(0).to(self.device)
            
            # Generate mesh
            with torch.no_grad():
                output = self.smplx_model(
                    betas=betas,
                    body_pose=body_pose,
                    global_orient=global_orient,
                )
                
                vertices = output.vertices.detach().cpu().numpy()[0]
                faces = self.smplx_model.faces
            
            # Create trimesh object
            mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
            
            # Export as GLB
            mesh.export(output_path)
            logger.info(f"Mesh exported successfully: {os.path.getsize(output_path)} bytes")
            
            return output_path
            
        except Exception as e:
            logger.error(f"Mesh export failed: {e}")
            logger.warning("Falling back to placeholder mesh")
            return self._export_placeholder_mesh(output_path)
    
    def _export_placeholder_mesh(self, output_path: str) -> str:
        """Create a placeholder mesh for testing"""
        body = trimesh.creation.capsule(radius=0.22, height=1.25, count=[16, 16])
        body.apply_translation([0, 0.9, 0])
        head = trimesh.creation.icosphere(subdivisions=2, radius=0.16)
        head.apply_translation([0, 1.65, 0])
        mesh = trimesh.util.concatenate([body, head])
        mesh.export(output_path)
        return output_path
