// UI wiring: drag & drop upload, preview, progress bar, GPU banner, downloads.

const dropzone = document.getElementById("dropzone");
const dropzoneEmpty = document.getElementById("dropzone-empty");
const fileInput = document.getElementById("file-input");
const browseBtn = document.getElementById("browse-btn");
const previewImage = document.getElementById("preview-image");
const generateBtn = document.getElementById("generate-btn");
const progressWrap = document.getElementById("progress-wrap");
const progressFill = document.getElementById("progress-fill");
const progressLabel = document.getElementById("progress-label");
const errorMessage = document.getElementById("error-message");
const gpuBanner = document.getElementById("gpu-banner");
const viewerPlaceholder = document.getElementById("viewer-placeholder");
const viewerControls = document.getElementById("viewer-controls");
const wireframeToggle = document.getElementById("wireframe-toggle");
const downloadLinks = {
  obj: document.getElementById("download-obj"),
  glb: document.getElementById("download-glb"),
  ply: document.getElementById("download-ply"),
};

let selectedFile = null;
let progressTimer = null;

function showError(message) {
  errorMessage.textContent = message;
  errorMessage.hidden = false;
}

function clearError() {
  errorMessage.hidden = true;
  errorMessage.textContent = "";
}

function setFile(file) {
  if (!file) return;
  if (!["image/png", "image/jpeg", "image/webp"].includes(file.type)) {
    showError("Formato no soportado. Usa una imagen PNG, JPEG o WEBP.");
    return;
  }
  clearError();
  selectedFile = file;
  previewImage.src = URL.createObjectURL(file);
  previewImage.hidden = false;
  dropzoneEmpty.hidden = true;
  generateBtn.disabled = false;
}

browseBtn.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", (e) => setFile(e.target.files[0]));

["dragenter", "dragover"].forEach((eventName) => {
  dropzone.addEventListener(eventName, (e) => {
    e.preventDefault();
    dropzone.classList.add("dropzone--active");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  dropzone.addEventListener(eventName, (e) => {
    e.preventDefault();
    dropzone.classList.remove("dropzone--active");
  });
});

dropzone.addEventListener("drop", (e) => {
  const file = e.dataTransfer.files[0];
  setFile(file);
});

// Fake but honest progress: TripoSR doesn't report intermediate steps, so we
// fill the bar over the typical ~30-60s generation window and let it settle
// at 90% until the server actually responds.
function startFakeProgress() {
  progressWrap.hidden = false;
  progressFill.style.width = "0%";
  progressLabel.textContent = "Generando modelo 3D... (puede tardar 30-60s)";
  const start = Date.now();
  const estimatedMs = 45000;
  progressTimer = setInterval(() => {
    const pct = Math.min(90, (100 * (Date.now() - start)) / estimatedMs);
    progressFill.style.width = `${pct}%`;
  }, 300);
}

function finishFakeProgress() {
  clearInterval(progressTimer);
  progressFill.style.width = "100%";
  setTimeout(() => {
    progressWrap.hidden = true;
  }, 400);
}

generateBtn.addEventListener("click", async () => {
  if (!selectedFile) return;
  clearError();
  generateBtn.disabled = true;
  startFakeProgress();

  const formData = new FormData();
  formData.append("file", selectedFile);

  try {
    const response = await fetch("/api/generate", { method: "POST", body: formData });
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Error generando el modelo 3D.");
    }

    progressLabel.textContent = `Modelo generado en ${data.generation_seconds}s`;
    finishFakeProgress();

    viewerPlaceholder.hidden = true;
    viewerControls.hidden = false;
    downloadLinks.obj.href = data.files.obj;
    downloadLinks.glb.href = data.files.glb;
    downloadLinks.ply.href = data.files.ply;
    wireframeToggle.checked = false;

    await window.viewer3D.loadModel(data.files.glb);
  } catch (err) {
    finishFakeProgress();
    showError(err.message || "No se pudo generar el modelo 3D.");
  } finally {
    generateBtn.disabled = false;
  }
});

wireframeToggle.addEventListener("change", (e) => {
  window.viewer3D.setWireframe(e.target.checked);
});

async function checkGpuStatus() {
  try {
    const response = await fetch("/api/gpu-status");
    const status = await response.json();
    if (!status.available) {
      gpuBanner.textContent =
        "⚠ No se detectó una GPU NVIDIA con CUDA. TripoSR necesita una GPU NVIDIA " +
        "(mínimo 8GB VRAM) para generar modelos 3D. La generación fallará hasta que " +
        "haya una GPU compatible disponible.";
      gpuBanner.classList.remove("banner--hidden");
      gpuBanner.classList.add("banner--error");
    } else if (status.reason) {
      gpuBanner.textContent = `⚠ ${status.reason}`;
      gpuBanner.classList.remove("banner--hidden");
      gpuBanner.classList.add("banner--warning");
    }
  } catch {
    // Backend not reachable yet; ignore, the user will see errors on generate.
  }
}

checkGpuStatus();
