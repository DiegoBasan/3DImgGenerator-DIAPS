"""Wrapper around TripoSR: GPU detection, lazy model loading and mesh generation.

TripoSR (https://github.com/VAST-AI-Research/TripoSR) is not published as a
regular PyPI package: you run it from its own source tree (the `tsr` Python
package that lives inside that repository). This module looks for that
source tree next to this project (see TRIPOSR_REPO_CANDIDATES) and adds it
to sys.path before importing it, so the rest of the app can stay agnostic
of how TripoSR itself is laid out. See README.md for setup instructions.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from pathlib import Path

import numpy as np
import torch
from PIL import Image

logger = logging.getLogger("triposr_app")

TRIPOSR_REPO_CANDIDATES = [
    Path(__file__).parent / "TripoSR",
    Path(__file__).parent / "third_party" / "TripoSR",
]

PRETRAINED_MODEL = "stabilityai/TripoSR"
MIN_RECOMMENDED_VRAM_GB = 8

# The NeRF renderer's chunk size trades VRAM for speed: TripoSR's own default
# (8192) targets 8GB+ cards. Override with the TRIPOSR_CHUNK_SIZE env var;
# lower it further (e.g. 512) on cards with less VRAM if you still hit
# out-of-memory errors.
DEFAULT_CHUNK_SIZE = int(os.environ.get("TRIPOSR_CHUNK_SIZE", "2048"))


class GPUNotAvailableError(RuntimeError):
    """No CUDA-capable GPU was detected."""


class TripoSRNotInstalledError(RuntimeError):
    """The TripoSR source tree (the `tsr` package) could not be found/imported."""


def check_gpu() -> dict:
    """Return a JSON-serializable summary of GPU/CUDA availability."""
    if not torch.cuda.is_available():
        return {
            "available": False,
            "device_name": None,
            "vram_gb": None,
            "reason": "No se detectó una GPU NVIDIA con soporte CUDA en este equipo.",
        }

    device_name = torch.cuda.get_device_name(0)
    vram_gb = round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 1)
    warning = None
    if vram_gb < MIN_RECOMMENDED_VRAM_GB:
        warning = (
            f"Tu GPU tiene {vram_gb}GB de VRAM; TripoSR recomienda al menos "
            f"{MIN_RECOMMENDED_VRAM_GB}GB. La generación podría fallar por falta de memoria."
        )
    return {"available": True, "device_name": device_name, "vram_gb": vram_gb, "reason": warning}


def _ensure_triposr_importable() -> None:
    """Make sure `import tsr` works, searching known local checkout locations."""
    try:
        import tsr  # noqa: F401

        return
    except ImportError:
        pass

    for candidate in TRIPOSR_REPO_CANDIDATES:
        if candidate.exists() and str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
            try:
                import tsr  # noqa: F401

                return
            except ImportError:
                continue

    raise TripoSRNotInstalledError(
        "No se encontró el código fuente de TripoSR. Clónalo dentro de este proyecto "
        "con:\n\n  git clone https://github.com/VAST-AI-Research/TripoSR.git\n\n"
        "y vuelve a intentarlo. Revisa la sección 'Instalación de TripoSR' en README.md."
    )


class TripoSRPipeline:
    """Thread-safe, lazily-initialized singleton around the TripoSR model."""

    _instance: "TripoSRPipeline | None" = None
    _lock = threading.Lock()

    def __init__(self, device: str):
        self.device = device
        self.model = None
        self.rembg_session = None

    @classmethod
    def get(cls) -> "TripoSRPipeline":
        """Return the shared pipeline instance, loading the model on first use."""
        with cls._lock:
            if cls._instance is None:
                gpu = check_gpu()
                if not gpu["available"]:
                    raise GPUNotAvailableError(
                        "No se detectó una GPU NVIDIA con soporte CUDA. TripoSR requiere "
                        "una GPU NVIDIA con al menos 8GB de VRAM (ideal 10GB+). Verifica "
                        "los drivers de NVIDIA y que PyTorch esté instalado con soporte CUDA "
                        "(torch.cuda.is_available() debe devolver True)."
                    )
                instance = cls(device="cuda")
                instance._load_model()
                cls._instance = instance
            return cls._instance

    def _load_model(self) -> None:
        """Download (first run only) and load TripoSR's pretrained weights."""
        _ensure_triposr_importable()
        from tsr.system import TSR
        import rembg

        logger.info("Cargando modelo TripoSR (%s)... esto puede tardar la primera vez.", PRETRAINED_MODEL)
        self.model = TSR.from_pretrained(
            PRETRAINED_MODEL,
            config_name="config.yaml",
            weight_name="model.ckpt",
        )
        self.model.renderer.set_chunk_size(DEFAULT_CHUNK_SIZE)
        self.model.to(self.device)
        self.rembg_session = rembg.new_session()
        logger.info(
            "Modelo TripoSR listo en %s (chunk_size=%d).", self.device, DEFAULT_CHUNK_SIZE
        )

    def generate(self, image: Image.Image, mesh_resolution: int = 256):
        """Run the full image -> 3D mesh pipeline and return a trimesh.Trimesh."""
        from tsr.utils import remove_background, resize_foreground

        image = remove_background(image.convert("RGB"), self.rembg_session)
        image = resize_foreground(image, 0.85)

        # Composite the now-transparent background onto flat gray, matching
        # TripoSR's own reference preprocessing (run.py in the TripoSR repo).
        image_arr = np.array(image).astype(np.float32) / 255.0
        image_arr = image_arr[:, :, :3] * image_arr[:, :, 3:4] + (1 - image_arr[:, :, 3:4]) * 0.5
        image = Image.fromarray((image_arr * 255.0).astype(np.uint8))

        torch.cuda.empty_cache()
        try:
            with torch.no_grad():
                scene_codes = self.model([image], device=self.device)
            meshes = self.model.extract_mesh(scene_codes, resolution=mesh_resolution)
        finally:
            torch.cuda.empty_cache()
        return meshes[0]
