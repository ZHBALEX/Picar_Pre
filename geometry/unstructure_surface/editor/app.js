(function () {
  const ids = [
    "shape", "radius", "points", "rx", "ry", "width", "height", "naca", "chord",
    "centerX", "centerY", "centerZ", "rotX", "rotY", "rotZ", "plane", "scale",
    "make3d", "thickness"
  ];
  const el = Object.fromEntries(ids.map((id) => [id, document.getElementById(id)]));
  const stats = document.getElementById("stats");
  const commandBox = document.getElementById("commandBox");
  const canvas = document.getElementById("fallbackCanvas");
  const viewer = document.getElementById("viewer");
  const rendererStatus = document.getElementById("rendererStatus");

  let three = null;
  let scene = null;
  let camera = null;
  let renderer = null;
  let meshObject = null;

  init();

  function init() {
    ids.forEach((id) => {
      el[id].addEventListener("input", update);
      el[id].addEventListener("change", update);
    });
    document.getElementById("downloadSurface").addEventListener("click", downloadSurface);
    document.getElementById("downloadStl").addEventListener("click", downloadStl);
    document.getElementById("copyCommand").addEventListener("click", copyCommand);
    window.addEventListener("resize", update);
    tryLoadThree();
    update();
  }

  async function tryLoadThree() {
    try {
      three = await import("https://unpkg.com/three@0.160.0/build/three.module.js");
      rendererStatus.textContent = "Three.js preview";
      scene = new three.Scene();
      scene.background = new three.Color(0xeef1ef);
      camera = new three.PerspectiveCamera(45, 1, 0.01, 10000);
      renderer = new three.WebGLRenderer({ antialias: true });
      renderer.setPixelRatio(window.devicePixelRatio || 1);
      viewer.appendChild(renderer.domElement);
      canvas.style.display = "none";
      const light = new three.DirectionalLight(0xffffff, 1.0);
      light.position.set(2, 3, 4);
      scene.add(light);
      scene.add(new three.AmbientLight(0xffffff, 0.6));
      scene.add(new three.GridHelper(4, 16, 0x87958f, 0xc8cfca));
      update();
    } catch (error) {
      rendererStatus.textContent = "Canvas preview";
    }
  }

  function readConfig() {
    return {
      shape: el.shape.value,
      radius: number(el.radius),
      points: Math.max(8, Math.floor(number(el.points))),
      rx: number(el.rx),
      ry: number(el.ry),
      width: number(el.width),
      height: number(el.height),
      naca: el.naca.value || "0012",
      chord: number(el.chord),
      center: [number(el.centerX), number(el.centerY), number(el.centerZ)],
      rotation: [number(el.rotX), number(el.rotY), number(el.rotZ)],
      plane: el.plane.value,
      scale: number(el.scale),
      make3d: el.make3d.checked,
      thickness: number(el.thickness),
    };
  }

  function update() {
    updateVisibleControls();
    const cfg = readConfig();
    const geom = buildGeometry(cfg);
    stats.textContent = `nodes ${geom.points.length} | elems ${geom.faces.length}`;
    commandBox.textContent = buildCommand(cfg);
    if (three && renderer) {
      renderThree(geom);
    } else {
      renderCanvas(geom);
    }
  }

  function updateVisibleControls() {
    const shape = el.shape.value;
    document.querySelectorAll("[data-shape]").forEach((node) => {
      node.style.display = node.dataset.shape.split(" ").includes(shape) ? "grid" : "none";
    });
  }

  function buildGeometry(cfg) {
    const boundary = buildBoundary(cfg);
    const points = cfg.make3d && cfg.thickness > 0 ? extrudePoints(boundary, cfg) : boundary;
    const faces = cfg.make3d && cfg.thickness > 0 ? sideWallFaces(boundary.length) : [];
    return { points, faces };
  }

  function buildBoundary(cfg) {
    let local;
    if (cfg.shape === "circle") {
      local = ellipsePoints(cfg.radius, cfg.radius, cfg.points);
    } else if (cfg.shape === "ellipse") {
      local = ellipsePoints(cfg.rx, cfg.ry, cfg.points);
    } else if (cfg.shape === "rectangle") {
      local = [
        [-cfg.width / 2, -cfg.height / 2, 0],
        [cfg.width / 2, -cfg.height / 2, 0],
        [cfg.width / 2, cfg.height / 2, 0],
        [-cfg.width / 2, cfg.height / 2, 0],
      ];
    } else {
      local = nacaPoints(cfg.naca, cfg.chord, cfg.points);
    }

    return local.map((p) => transformPoint(placeInPlane(p, cfg.plane), cfg));
  }

  function ellipsePoints(rx, ry, n) {
    const pts = [];
    for (let i = 0; i < n; i += 1) {
      const t = (2 * Math.PI * i) / n;
      pts.push([rx * Math.cos(t), ry * Math.sin(t), 0]);
    }
    return pts;
  }

  function nacaPoints(code, chord, n) {
    const clean = /^[0-9]{4}$/.test(code) ? code : "0012";
    const m = Number(clean[0]) / 100;
    const p = Number(clean[1]) / 10;
    const t = Number(clean.slice(2)) / 100;
    const upper = [];
    const lower = [];
    for (let i = 0; i < n; i += 1) {
      const beta = Math.PI * i / Math.max(1, n - 1);
      const x = 0.5 * (1 - Math.cos(beta));
      const yt = 5 * t * (0.2969 * Math.sqrt(x) - 0.1260 * x - 0.3516 * x ** 2 + 0.2843 * x ** 3 - 0.1015 * x ** 4);
      let yc = 0;
      let dy = 0;
      if (m > 0 && p > 0) {
        if (x < p) {
          yc = (m / p ** 2) * (2 * p * x - x ** 2);
          dy = (2 * m / p ** 2) * (p - x);
        } else {
          yc = (m / (1 - p) ** 2) * ((1 - 2 * p) + 2 * p * x - x ** 2);
          dy = (2 * m / (1 - p) ** 2) * (p - x);
        }
      }
      const theta = Math.atan(dy);
      upper.push([(x - yt * Math.sin(theta) - 0.5) * chord, (yc + yt * Math.cos(theta)) * chord, 0]);
      lower.push([(x + yt * Math.sin(theta) - 0.5) * chord, (yc - yt * Math.cos(theta)) * chord, 0]);
    }
    return upper.reverse().concat(lower.slice(1));
  }

  function placeInPlane(p, plane) {
    if (plane === "xy") return [p[0], p[1], p[2]];
    if (plane === "xz") return [p[0], p[2], p[1]];
    return [p[2], p[0], p[1]];
  }

  function transformPoint(point, cfg) {
    let p = point.map((v) => v * cfg.scale);
    const [rx, ry, rz] = cfg.rotation.map((v) => v * Math.PI / 180);
    p = rotateX(p, rx);
    p = rotateY(p, ry);
    p = rotateZ(p, rz);
    return [p[0] + cfg.center[0], p[1] + cfg.center[1], p[2] + cfg.center[2]];
  }

  function extrudePoints(boundary, cfg) {
    const axis = cfg.plane === "xy" ? 2 : cfg.plane === "xz" ? 1 : 0;
    const d = cfg.thickness / 2;
    const bottom = boundary.map((p) => offsetAxis(p, axis, -d));
    const top = boundary.map((p) => offsetAxis(p, axis, d));
    return bottom.concat(top);
  }

  function sideWallFaces(n) {
    const faces = [];
    for (let a = 0; a < n; a += 1) {
      const b = a === n - 1 ? 0 : a + 1;
      faces.push([a, b, b + n]);
      faces.push([a, b + n, a + n]);
    }
    return faces;
  }

  function renderThree(geom) {
    const rect = viewer.getBoundingClientRect();
    renderer.setSize(rect.width, rect.height);
    camera.aspect = rect.width / Math.max(1, rect.height);
    camera.updateProjectionMatrix();
    if (meshObject) scene.remove(meshObject);

    if (geom.faces.length) {
      const positions = [];
      geom.faces.forEach((f) => f.forEach((i) => positions.push(...geom.points[i])));
      const g = new three.BufferGeometry();
      g.setAttribute("position", new three.Float32BufferAttribute(positions, 3));
      g.computeVertexNormals();
      meshObject = new three.Mesh(g, new three.MeshStandardMaterial({ color: 0x2f7d68, side: three.DoubleSide, roughness: 0.55 }));
    } else {
      const positions = geom.points.flat();
      const g = new three.BufferGeometry();
      g.setAttribute("position", new three.Float32BufferAttribute(positions, 3));
      meshObject = new three.Points(g, new three.PointsMaterial({ color: 0x2f7d68, size: 0.035 }));
    }
    scene.add(meshObject);
    frameCamera(geom.points);
    renderer.render(scene, camera);
  }

  function renderCanvas(geom) {
    const rect = viewer.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.max(1, Math.floor(rect.width * dpr));
    canvas.height = Math.max(1, Math.floor(rect.height * dpr));
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, rect.width, rect.height);
    ctx.fillStyle = "#eef1ef";
    ctx.fillRect(0, 0, rect.width, rect.height);
    const bounds = getBounds(geom.points);
    const pad = 40;
    const sx = (rect.width - pad * 2) / Math.max(1e-9, bounds.max[0] - bounds.min[0]);
    const sy = (rect.height - pad * 2) / Math.max(1e-9, bounds.max[1] - bounds.min[1]);
    const s = Math.min(sx, sy);
    const map = (p) => [pad + (p[0] - bounds.min[0]) * s, rect.height - pad - (p[1] - bounds.min[1]) * s];
    ctx.strokeStyle = "#2f7d68";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    geom.points.forEach((p, i) => {
      const [x, y] = map(p);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    if (!geom.faces.length) ctx.closePath();
    ctx.stroke();
    ctx.fillStyle = "#215948";
    geom.points.forEach((p) => {
      const [x, y] = map(p);
      ctx.beginPath();
      ctx.arc(x, y, 2.5, 0, Math.PI * 2);
      ctx.fill();
    });
  }

  function frameCamera(points) {
    const b = getBounds(points);
    const center = [(b.min[0] + b.max[0]) / 2, (b.min[1] + b.max[1]) / 2, (b.min[2] + b.max[2]) / 2];
    const span = Math.max(b.max[0] - b.min[0], b.max[1] - b.min[1], b.max[2] - b.min[2], 1);
    camera.position.set(center[0] + span, center[1] - span * 1.5, center[2] + span);
    camera.lookAt(center[0], center[1], center[2]);
    camera.near = span / 100;
    camera.far = span * 100;
  }

  function buildSurfaceText() {
    const geom = buildGeometry(readConfig());
    const lines = [" ", `${pad(geom.points.length, 12)}${pad(geom.faces.length, 12)}`, " "];
    geom.points.forEach((p, i) => {
      lines.push(`${pad(i + 1, 12)}   ${p[0].toFixed(14)}        ${p[1].toFixed(14)}     `);
      lines.push(`   ${p[2].toFixed(14)}     `);
    });
    lines.push(" ");
    geom.faces.forEach((f, i) => lines.push(`${pad(i + 1, 12)}${pad(f[0] + 1, 12)}${pad(f[1] + 1, 12)}${pad(f[2] + 1, 12)}`));
    lines.push(" ", " -100.000  -100.000  -100.000", "");
    return lines.join("\n");
  }

  function buildStlText() {
    const geom = buildGeometry(readConfig());
    const faces = geom.faces.length ? geom.faces : [];
    const lines = ["solid surface_editor"];
    faces.forEach((f) => {
      const a = geom.points[f[0]], b = geom.points[f[1]], c = geom.points[f[2]];
      const n = normal(a, b, c);
      lines.push(`  facet normal ${n[0]} ${n[1]} ${n[2]}`);
      lines.push("    outer loop");
      [a, b, c].forEach((p) => lines.push(`      vertex ${p[0]} ${p[1]} ${p[2]}`));
      lines.push("    endloop", "  endfacet");
    });
    lines.push("endsolid surface_editor", "");
    return lines.join("\n");
  }

  function downloadSurface() {
    download("unstruc_surface_in.dat", buildSurfaceText(), "text/plain");
  }

  function downloadStl() {
    const cfg = readConfig();
    if (!cfg.make3d) {
      alert("STL export needs a 3D side-wall surface. Enable thickness first.");
      return;
    }
    download("surface_editor.stl", buildStlText(), "model/stl");
  }

  function copyCommand() {
    navigator.clipboard.writeText(commandBox.textContent || "");
  }

  function buildCommand(cfg) {
    const params = [];
    if (cfg.shape === "circle") params.push(`--param radius=${cfg.radius}`, `--param n=${cfg.points}`);
    if (cfg.shape === "ellipse") params.push(`--param rx=${cfg.rx}`, `--param ry=${cfg.ry}`, `--param n=${cfg.points}`);
    if (cfg.shape === "rectangle") params.push(`--param width=${cfg.width}`, `--param height=${cfg.height}`);
    if (cfg.shape === "naca") params.push(`--param code=${cfg.naca}`, `--param chord=${cfg.chord}`, `--param n=${cfg.points}`);
    const parts = [
      "python geometry/unstructure_surface/run_surface_tools.py",
      "--case-dir path/to/case",
      "generate",
      cfg.shape,
      ...params,
      "--center", ...cfg.center,
      "--plane", cfg.plane,
    ];
    if (cfg.make3d) parts.push("--thickness", cfg.thickness);
    if (cfg.rotation.some((v) => v !== 0)) parts.push("--rotate", ...cfg.rotation);
    if (cfg.scale !== 1) parts.push("--scale", cfg.scale);
    return parts.join(" ");
  }

  function download(name, text, type) {
    const blob = new Blob([text], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
    URL.revokeObjectURL(url);
  }

  function number(input) {
    return Number(input.value || 0);
  }

  function offsetAxis(p, axis, d) {
    const q = p.slice();
    q[axis] += d;
    return q;
  }

  function rotateX(p, a) {
    const c = Math.cos(a), s = Math.sin(a);
    return [p[0], p[1] * c - p[2] * s, p[1] * s + p[2] * c];
  }

  function rotateY(p, a) {
    const c = Math.cos(a), s = Math.sin(a);
    return [p[0] * c + p[2] * s, p[1], -p[0] * s + p[2] * c];
  }

  function rotateZ(p, a) {
    const c = Math.cos(a), s = Math.sin(a);
    return [p[0] * c - p[1] * s, p[0] * s + p[1] * c, p[2]];
  }

  function getBounds(points) {
    const min = [Infinity, Infinity, Infinity];
    const max = [-Infinity, -Infinity, -Infinity];
    points.forEach((p) => {
      for (let i = 0; i < 3; i += 1) {
        min[i] = Math.min(min[i], p[i]);
        max[i] = Math.max(max[i], p[i]);
      }
    });
    return { min, max };
  }

  function normal(a, b, c) {
    const u = [b[0] - a[0], b[1] - a[1], b[2] - a[2]];
    const v = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
    const n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]];
    const len = Math.hypot(n[0], n[1], n[2]) || 1;
    return [n[0] / len, n[1] / len, n[2] / len];
  }

  function pad(value, width) {
    return String(value).padStart(width, " ");
  }
}());
