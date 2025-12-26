import * as THREE from "three";

export class BasicScene {
  private renderer: THREE.WebGLRenderer;
  private scene: THREE.Scene;
  private camera: THREE.PerspectiveCamera;
  private rafId: number | null = null;
  private resizeObserver: ResizeObserver;

  constructor(private mount: HTMLElement) {
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color("#0c1422");

    this.camera = new THREE.PerspectiveCamera(55, 1, 0.1, 100);
    this.camera.position.set(0, 1.2, 2.4);

    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.mount.appendChild(this.renderer.domElement);

    const light = new THREE.DirectionalLight(0xffffff, 1.1);
    light.position.set(2, 4, 3);
    this.scene.add(light);
    this.scene.add(new THREE.AmbientLight(0xffffff, 0.3));

    const avatar = new THREE.Mesh(
      new THREE.CapsuleGeometry(0.25, 0.8, 6, 12),
      new THREE.MeshStandardMaterial({ color: "#7aa2ff", roughness: 0.35, metalness: 0.05 })
    );
    avatar.position.set(0, 0.6, 0);
    this.scene.add(avatar);

    const garment = new THREE.Mesh(
      new THREE.BoxGeometry(0.75, 1.2, 0.35),
      new THREE.MeshStandardMaterial({ color: "#ffffff", transparent: true, opacity: 0.18 })
    );
    garment.position.set(0, 0.72, 0);
    this.scene.add(garment);

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
    this.scene.rotation.y += 0.003;
    this.renderer.render(this.scene, this.camera);
  };

  destroy() {
    if (this.rafId) cancelAnimationFrame(this.rafId);
    this.resizeObserver.disconnect();
    this.renderer.dispose();
    this.mount.innerHTML = "";
  }
}

