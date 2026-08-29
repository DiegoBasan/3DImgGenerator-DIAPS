# 3DImgGenerator-DIAPS

Aplicación local (Python + HTML) que convierte una imagen en un modelo 3D usando
[TripoSR](https://github.com/VAST-AI-Research/TripoSR). Todo corre en tu máquina:
sin APIs de pago ni servicios externos (más allá de la descarga única de los
pesos del modelo la primera vez que lo usas).

- **Backend:** FastAPI (`main.py`) + TripoSR (`pipeline.py`)
- **Frontend:** HTML + Three.js (drag & drop, preview, barra de progreso, visor 3D)

## Requisitos del sistema

- **GPU:** NVIDIA con CUDA, mínimo 8GB de VRAM (ideal 10GB+). Sin GPU compatible,
  la app arranca igual pero `/generate` responde con un error claro explicando
  el motivo.
- **RAM:** 16GB mínimo.
- **Almacenamiento:** ~20GB libres (pesos del modelo + dependencias + salidas).
- **Python:** 3.10 u 3.11.
- **CUDA Toolkit / drivers NVIDIA** instalados y funcionando (`nvidia-smi` debe
  mostrar tu GPU).

## Instalación

### 1. Clonar este repositorio

```bash
git clone https://github.com/DiegoBasan/3DImgGenerator-DIAPS.git
cd 3DImgGenerator-DIAPS
```

### 2. Instalar TripoSR

TripoSR no se distribuye como paquete de PyPI: se usa clonando su propio
repositorio. Clónalo **dentro** de la carpeta del proyecto:

```bash
git clone https://github.com/VAST-AI-Research/TripoSR.git
```

Debe quedar como `TripoSR/` junto a `main.py` (esta carpeta está en
`.gitignore`, no se sube al repo).

### 3. Instalar dependencias de Python

Primero instala PyTorch con soporte CUDA para tu versión de CUDA, siguiendo
[pytorch.org/get-started/locally](https://pytorch.org/get-started/locally/),
por ejemplo para CUDA 12.1:

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

Luego instala el resto:

```bash
pip install -r requirements.txt
```

> `torchmcubes` (usado por TripoSR para extraer la malla) se compila desde
> código fuente; necesitas un compilador de C++ instalado (en Linux, `build-essential`;
> en Windows, "Build Tools for Visual Studio").

### 4. Ejecutar

```bash
python main.py
```

Abre **http://localhost:8000** en el navegador. La primera generación
descargará automáticamente los pesos de TripoSR desde Hugging Face
(`stabilityai/TripoSR`, unos pocos GB) — puede tardar varios minutos según tu
conexión. Las siguientes generaciones tardan ~30-60 segundos, según tu GPU.

## Uso

1. Arrastra una imagen (PNG/JPEG/WEBP) al recuadro, o haz clic en "Elegir archivo".
2. Pulsa **Generar 3D**.
3. Espera a que se complete la barra de progreso (30-60s aprox.).
4. Explora el modelo en el visor 3D: arrastra para orbitar, scroll para zoom.
5. Activa **Wireframe** para ver la malla, o descarga el resultado en
   `.obj`, `.glb` o `.ply`.

## Estructura

```
3DImgGenerator-DIAPS/
├── main.py              # App FastAPI: endpoints /, /api/gpu-status, /api/generate
├── pipeline.py           # Carga perezosa de TripoSR, chequeo de GPU, generación de malla
├── index.html            # Interfaz (drag&drop, preview, progreso, visor)
├── static/
│   ├── style.css
│   ├── viewer.js         # Escena Three.js: cámara, luces, carga de GLB, wireframe
│   └── app.js            # Lógica de subida de imagen, progreso, descargas
├── models/               # Modelos 3D generados (uno por job, en subcarpetas con UUID)
├── requirements.txt
└── .gitignore
```

## Solución de problemas

- **"No se detectó una GPU NVIDIA con soporte CUDA"**: verifica `nvidia-smi` y
  que `python -c "import torch; print(torch.cuda.is_available())"` devuelva
  `True`. Si devuelve `False` con una GPU NVIDIA presente, reinstala PyTorch
  con el índice CUDA correcto (paso 3).
- **"No se encontró el código fuente de TripoSR"**: falta el paso 2 — clona
  `TripoSR` dentro de la carpeta del proyecto.
- **Out of memory (GPU)**: cierra otras apps que usen la GPU, o usa una imagen
  más pequeña. TripoSR necesita ~6-8GB de VRAM libres como mínimo.
- **La generación falla al compilar `torchmcubes`**: instala un compilador de
  C++ (`build-essential` en Debian/Ubuntu, Build Tools de Visual Studio en
  Windows) y vuelve a intentar `pip install -r requirements.txt`.

## Notas

- El fondo de la imagen se elimina automáticamente (`rembg`) antes de generar
  el modelo, siguiendo el preprocesado de referencia de TripoSR.
- Cada generación crea una subcarpeta en `models/<job_id>/` con `model.obj`,
  `model.glb` y `model.ply`. Estos archivos no se versionan en git.
