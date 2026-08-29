"""FastAPI backend for the local image-to-3D app.

Run with:  python main.py
Then open: http://localhost:8000
"""

from __future__ import annotations

import io
import logging
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError

from pipeline import GPUNotAvailableError, TripoSRNotInstalledError, TripoSRPipeline, check_gpu

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("triposr_app")

BASE_DIR = Path(__file__).parent
MODELS_DIR = BASE_DIR / "models"
MODELS_DIR.mkdir(exist_ok=True)

ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg", "image/webp"}
MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB

app = FastAPI(title="Image to 3D (TripoSR)")

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.mount("/models", StaticFiles(directory=MODELS_DIR), name="models")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(BASE_DIR / "index.html")


@app.get("/api/gpu-status")
def gpu_status() -> dict:
    """Frontend calls this on load to show a clear warning if there's no usable GPU."""
    return check_gpu()


@app.post("/api/generate")
def generate(file: UploadFile = File(...)) -> JSONResponse:
    """Receive an image, run it through TripoSR, and return download URLs for the mesh."""
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Formato de imagen no soportado ({file.content_type}). Usa PNG, JPEG o WEBP.",
        )

    raw_bytes = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="La imagen supera el límite de 15MB.")

    try:
        image = Image.open(io.BytesIO(raw_bytes))
        image.load()
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=400, detail="El archivo no es una imagen válida.") from exc

    try:
        pipeline = TripoSRPipeline.get()
    except GPUNotAvailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except TripoSRNotInstalledError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    job_id = uuid.uuid4().hex[:12]
    job_dir = MODELS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    logger.info("[%s] Generando modelo 3D a partir de '%s'...", job_id, file.filename)
    start = time.time()
    try:
        mesh = pipeline.generate(image)
    except RuntimeError as exc:
        if "out of memory" in str(exc).lower():
            raise HTTPException(
                status_code=503,
                detail="La GPU se quedó sin memoria (out of memory) generando el modelo. "
                "Cierra otras aplicaciones que usen la GPU e inténtalo de nuevo.",
            ) from exc
        logger.exception("[%s] Error de runtime generando el modelo 3D", job_id)
        raise HTTPException(status_code=500, detail=f"Error generando el modelo 3D: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 - surfaced to the user as a clear API error
        logger.exception("[%s] Fallo inesperado generando el modelo 3D", job_id)
        raise HTTPException(status_code=500, detail=f"Error generando el modelo 3D: {exc}") from exc

    elapsed = round(time.time() - start, 1)
    logger.info("[%s] Modelo 3D generado en %.1fs", job_id, elapsed)

    obj_path = job_dir / "model.obj"
    glb_path = job_dir / "model.glb"
    ply_path = job_dir / "model.ply"
    mesh.export(obj_path)
    mesh.export(glb_path)
    mesh.export(ply_path)

    return JSONResponse(
        {
            "job_id": job_id,
            "generation_seconds": elapsed,
            "files": {
                "obj": f"/models/{job_id}/model.obj",
                "glb": f"/models/{job_id}/model.glb",
                "ply": f"/models/{job_id}/model.ply",
            },
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
