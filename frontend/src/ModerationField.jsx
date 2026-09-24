import { useEffect, useRef } from "react";
import * as THREE from "three";

/**
 * Three.js hero: a live "moderation field" — one point per recent judge call,
 * colored by layer, orbiting a central core. Reads real data: pass `points`
 * as [{layer}] and it renders them. Pure canvas, no external assets.
 */
export default function ModerationField({ points = [], height = 260 }) {
  const ref = useRef(null);
  const stateRef = useRef({ raf: 0, renderer: null, scene: null, camera: null });

  useEffect(() => {
    const host = ref.current;
    if (!host) return;

    const scene = new THREE.Scene();
    const w = host.clientWidth || 800;
    const camera = new THREE.PerspectiveCamera(50, w / height, 0.1, 100);
    camera.position.set(0, 0, 9);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(w, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    host.appendChild(renderer.domElement);

    scene.add(new THREE.AmbientLight(0xffffff, 0.7));
    const key = new THREE.PointLight(0x6ee7b7, 40, 40);
    key.position.set(4, 4, 6);
    scene.add(key);

    // central core — the bot
    const core = new THREE.Mesh(
      new THREE.IcosahedronGeometry(1.15, 1),
      new THREE.MeshStandardMaterial({
        color: 0x6ee7b7, roughness: 0.35, metalness: 0.25,
        emissive: 0x1c4a3a, emissiveIntensity: 0.7, flatShading: true,
      })
    );
    scene.add(core);

    // wire halo
    const halo = new THREE.Mesh(
      new THREE.IcosahedronGeometry(1.7, 1),
      new THREE.MeshBasicMaterial({ color: 0x818cf8, wireframe: true,
                                    transparent: true, opacity: 0.22 })
    );
    scene.add(halo);

    // judge-call points on a sphere, colored by layer
    const COLORS = { jev: 0x6ee7b7, opencode: 0x818cf8, heuristic: 0xf5b95f };
    const group = new THREE.Group();
    const n = Math.max(points.length, 24);
    for (let i = 0; i < n; i++) {
      const layer = points[i]?.layer || "jev";
      const phi = Math.acos(1 - (2 * (i + 0.5)) / n);
      const theta = Math.PI * (1 + Math.sqrt(5)) * i;
      const r = 3.1 + ((i * 37) % 10) / 22;
      const p = new THREE.Vector3(
        r * Math.sin(phi) * Math.cos(theta),
        r * Math.sin(phi) * Math.sin(theta),
        r * Math.cos(phi)
      );
      const m = new THREE.Mesh(
        new THREE.SphereGeometry(0.07 + ((i * 13) % 6) / 190, 10, 10),
        new THREE.MeshStandardMaterial({
          color: COLORS[layer] ?? 0x9aa3b2, emissive: COLORS[layer] ?? 0x333333,
          emissiveIntensity: 0.55, roughness: 0.5,
        })
      );
      m.position.copy(p);
      group.add(m);
    }
    scene.add(group);

    // slow drift + subtle parallax from pointer
    let px = 0, py = 0, tx = 0, ty = 0;
    const onMove = (e) => {
      const rect = host.getBoundingClientRect();
      tx = ((e.clientX - rect.left) / rect.width - 0.5) * 0.8;
      ty = ((e.clientY - rect.top) / rect.height - 0.5) * 0.8;
    };
    window.addEventListener("pointermove", onMove);

    const clock = new THREE.Clock();
    const tick = () => {
      const t = clock.getElapsedTime();
      core.rotation.y = t * 0.25;
      core.rotation.x = Math.sin(t * 0.35) * 0.15;
      halo.rotation.y = -t * 0.18;
      halo.rotation.z = t * 0.09;
      group.rotation.y = t * 0.07;
      px += (tx - px) * 0.05; py += (ty - py) * 0.05;
      camera.position.x = px * 2.2;
      camera.position.y = -py * 2.2;
      camera.lookAt(0, 0, 0);
      renderer.render(scene, camera);
      stateRef.current.raf = requestAnimationFrame(tick);
    };
    tick();

    const onResize = () => {
      const nw = host.clientWidth || w;
      camera.aspect = nw / height;
      camera.updateProjectionMatrix();
      renderer.setSize(nw, height);
    };
    window.addEventListener("resize", onResize);

    stateRef.current = { ...stateRef.current, renderer, scene, camera };
    return () => {
      cancelAnimationFrame(stateRef.current.raf);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("resize", onResize);
      renderer.dispose();
      scene.traverse((o) => {
        if (o.geometry) o.geometry.dispose();
        if (o.material) (Array.isArray(o.material) ? o.material : [o.material])
          .forEach((mm) => mm.dispose());
      });
      if (host.contains(renderer.domElement)) host.removeChild(renderer.domElement);
    };
  }, [JSON.stringify(points.map((p) => p.layer))]);

  return <div className="three-host" ref={ref} style={{ height }} aria-hidden="true" />;
}
