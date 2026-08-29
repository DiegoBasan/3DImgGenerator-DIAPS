// Three.js viewer: scene, camera, lighting and GLB loading/wireframe toggle.
// Exposed on window.viewer3D so app.js (upload/UI logic) can drive it.

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

class Viewer3D {
  constructor(canvas) {
    this.canvas = canvas;
    this.container = canvas.parentElement;
    this.currentModel = null;

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x1b1d22);

    this.camera = new THREE.PerspectiveCamera(45, 1, 0.01, 1000);
    this.camera.position.set(2, 1.5, 2.5);

    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;

    this._setupLights();
    this._resize();
    window.addEventListener("resize", () => this._resize());

    this.renderer.setAnimationLoop(() => {
      this.controls.update();
      this.renderer.render(this.scene, this.camera);
    });
  }

  _setupLights() {
    this.scene.add(new THREE.AmbientLight(0xffffff, 0.6));

    const key = new THREE.DirectionalLight(0xffffff, 1.2);
    key.position.set(3, 5, 4);
    this.scene.add(key);

    const fill = new THREE.DirectionalLight(0xffffff, 0.4);
    fill.position.set(-4, 2, -3);
    this.scene.add(fill);
  }

  _resize() {
    const { clientWidth, clientHeight } = this.container;
    if (clientWidth === 0 || clientHeight === 0) return;
    this.camera.aspect = clientWidth / clientHeight;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(clientWidth, clientHeight, false);
  }

  /** Load a GLB model from a URL, replacing whatever is currently shown. */
  loadModel(url) {
    return new Promise((resolve, reject) => {
      const loader = new GLTFLoader();
      loader.load(
        url,
        (gltf) => {
          this._clearModel();
          this.currentModel = gltf.scene;
          this._frameModel(this.currentModel);
          this.scene.add(this.currentModel);
          resolve();
        },
        undefined,
        (error) => reject(error)
      );
    });
  }

  _clearModel() {
    if (!this.currentModel) return;
    this.scene.remove(this.currentModel);
    this.currentModel.traverse((child) => {
      if (child.geometry) child.geometry.dispose();
      if (child.material) child.material.dispose();
    });
    this.currentModel = null;
  }

  /** Center the model at the origin, scale it to fit, and point the camera at it. */
  _frameModel(model) {
    const box = new THREE.Box3().setFromObject(model);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());

    const maxDim = Math.max(size.x, size.y, size.z) || 1;
    const scale = 1.5 / maxDim;
    model.scale.setScalar(scale);

    const scaledCenter = center.clone().multiplyScalar(scale);
    model.position.sub(scaledCenter);

    this.camera.position.set(2, 1.5, 2.5);
    this.controls.target.set(0, 0, 0);
    this.controls.update();
  }

  setWireframe(enabled) {
    if (!this.currentModel) return;
    this.currentModel.traverse((child) => {
      if (child.isMesh && child.material) {
        child.material.wireframe = enabled;
      }
    });
  }
}

window.viewer3D = new Viewer3D(document.getElementById("viewer-canvas"));
