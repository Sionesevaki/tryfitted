import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { MeshoptDecoder } from "three/examples/jsm/libs/meshopt_decoder.module.js";

export class AvatarScene {
  private renderer: THREE.WebGLRenderer;
  private scene: THREE.Scene;
  private camera: THREE.PerspectiveCamera;
  private controls: OrbitControls;
  private loader: GLTFLoader;
  private rafId: number | null = null;
  private resizeObserver: ResizeObserver;
  private modelRoot: THREE.Object3D | null = null;
  private helpers: THREE.Object3D[] = [];
  private flipVertical = false;

  constructor(private mount: HTMLElement) {
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color("#0c1422");

    this.camera = new THREE.PerspectiveCamera(55, 1, 0.01, 1000);
    this.camera.position.set(0.5, 1.2, 2.2);

    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.domElement.style.width = "100%";
    this.renderer.domElement.style.height = "100%";
    this.renderer.domElement.style.display = "block";
    this.mount.appendChild(this.renderer.domElement);

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.06;
    this.controls.target.set(0, 1.0, 0);
    this.controls.update();

    this.loader = new GLTFLoader();
    this.loader.setMeshoptDecoder(MeshoptDecoder);

    const keyLight = new THREE.DirectionalLight(0xffffff, 1.2);
    keyLight.position.set(2, 4, 3);
    this.scene.add(keyLight);

    const fillLight = new THREE.DirectionalLight(0xffffff, 0.4);
    fillLight.position.set(-2, 2, -1);
    this.scene.add(fillLight);

    this.scene.add(new THREE.AmbientLight(0xffffff, 0.25));

    const grid = new THREE.GridHelper(4, 20, 0x334155, 0x1f2937);
    grid.position.y = 0;
    grid.material.transparent = true;
    (grid.material as THREE.Material).opacity = 0.25;
    this.scene.add(grid);
    this.helpers.push(grid);

    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(this.mount);
    this.resize();
    this.loop();
  }

  private resize() {
    const w = this.mount.clientWidth;
    const h = this.mount.clientHeight;
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h, false);
  }

  private loop = () => {
    this.rafId = requestAnimationFrame(this.loop);
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
  };

  private clearModel() {
    if (!this.modelRoot) return;
    this.scene.remove(this.modelRoot);
    this.modelRoot.traverse((obj) => {
      const mesh = obj as THREE.Mesh;
      if (mesh.geometry) mesh.geometry.dispose();
      const material = (mesh as any).material as THREE.Material | THREE.Material[] | undefined;
      if (Array.isArray(material)) material.forEach((m) => m.dispose());
      else material?.dispose();
    });
    this.modelRoot = null;
  }

  async load(glbUrl: string) {
    this.clearModel();

    const gltfScene = await new Promise<THREE.Object3D>((resolve, reject) => {
      this.loader.load(
        glbUrl,
        (g) => resolve(g.scene ?? g.scenes?.[0]),
        undefined,
        (err) => reject(err)
      );
    });

    this.modelRoot = gltfScene;
    this.applyModelTransform();
    this.scene.add(gltfScene);
    this.fitCameraToObject(gltfScene);
  }

  setFlipVertical(flip: boolean) {
    this.flipVertical = flip;
    if (!this.modelRoot) return;
    this.applyModelTransform();
    this.fitCameraToObject(this.modelRoot);
  }

  private applyModelTransform() {
    if (!this.modelRoot) return;
    this.modelRoot.rotation.set(this.flipVertical ? Math.PI : 0, 0, 0);
  }

  private fitCameraToObject(root: THREE.Object3D) {
    const box = new THREE.Box3().setFromObject(root);
    const size = new THREE.Vector3();
    const center = new THREE.Vector3();
    box.getSize(size);
    box.getCenter(center);

    const maxDim = Math.max(size.x, size.y, size.z);
    const fov = (this.camera.fov * Math.PI) / 180;
    const cameraDistance = maxDim / (2 * Math.tan(fov / 2));

    const direction = new THREE.Vector3(0.8, 0.4, 1).normalize();
    this.camera.position.copy(center.clone().add(direction.multiplyScalar(cameraDistance * 1.6)));
    this.camera.near = Math.max(0.01, cameraDistance / 100);
    this.camera.far = cameraDistance * 100;
    this.camera.updateProjectionMatrix();

    this.controls.target.copy(center);
    this.controls.update();
  }

  destroy() {
    if (this.rafId) cancelAnimationFrame(this.rafId);
    this.resizeObserver.disconnect();
    this.controls.dispose();
    this.clearModel();
    this.helpers.forEach((h) => this.scene.remove(h));
    this.helpers = [];
    this.renderer.dispose();
    this.mount.innerHTML = "";
  }
}
