(function () {
  const ids = [
    "shape", "radius", "points", "rx", "ry", "width", "height", "naca", "chord",
    "centerX", "centerY", "centerZ", "rotX", "rotY", "rotZ", "plane", "scale",
    "make3d", "thickness", "layers", "remesh3d", "maxEdge", "layerSpacing"
  ];
  const el = Object.fromEntries(ids.map((id) => [id, document.getElementById(id)]));
  const stats = document.getElementById("stats");
  const commandBox = document.getElementById("commandBox");
  const canvas = document.getElementById("fallbackCanvas");
  const viewer = document.getElementById("viewer");
  const viewerHelp = document.getElementById("viewerHelp");
  const cursorReadout = document.getElementById("cursorReadout");
  const rendererStatus = document.getElementById("rendererStatus");
  const mode2dButton = document.getElementById("mode2d");
  const mode3dButton = document.getElementById("mode3d");
  const viewIsoButton = document.getElementById("viewIso");
  const viewTopButton = document.getElementById("viewTop");
  const fitViewButton = document.getElementById("fitView");

  let three = null;
  let scene = null;
  let camera = null;
  let renderer = null;
  let objectGroup = null;
  let axes = null;
  let grid = null;
  let currentGeometry = null;
  let viewMode = "2d";
  let needsFrame = true;
  let needs3dFit = true;
  let keep2dView = false;

  const view2d = {
    scale: 1,
    offset: [0, 0],
    dragging: false,
    action: "pan",
    activeHandle: null,
    hoverHandle: null,
    startWorld: [0, 0],
    startCenter: [0, 0, 0],
    startValue: 0,
    x: 0,
    y: 0,
    fittedKey: "",
  };

  const orbit = {
    target: [0, 0, 0],
    yaw: -0.72,
    pitch: 0.62,
    distance: 1,
    dragging: false,
    button: 0,
    x: 0,
    y: 0,
  };

  init();

  function init() {
    ids.forEach((id) => {
      el[id].addEventListener("input", update);
      el[id].addEventListener("change", update);
    });
    document.getElementById("downloadSurface").addEventListener("click", downloadSurface);
    document.getElementById("downloadStl").addEventListener("click", downloadStl);
    document.getElementById("copyCommand").addEventListener("click", copyCommand);
    mode2dButton.addEventListener("click", () => setViewMode("2d"));
    mode3dButton.addEventListener("click", () => setViewMode("3d"));
    viewIsoButton.addEventListener("click", () => setPresetView("iso"));
    viewTopButton.addEventListener("click", () => setPresetView("top"));
    fitViewButton.addEventListener("click", () => fitCurrentView(true));
    viewer.addEventListener("contextmenu", (event) => event.preventDefault());
    viewer.addEventListener("pointerdown", onPointerDown);
    viewer.addEventListener("pointermove", onPointerMove);
    viewer.addEventListener("pointerup", onPointerUp);
    viewer.addEventListener("pointercancel", onPointerUp);
    viewer.addEventListener("wheel", onWheel, { passive: false });
    window.addEventListener("resize", () => {
      fitCurrentView(true);
      update();
    });
    setViewMode("2d");
    tryLoadThree();
    update();
  }

  async function tryLoadThree() {
    try {
      three = await import("https://unpkg.com/three@0.160.0/build/three.module.js");
      scene = new three.Scene();
      scene.background = new three.Color(0xeef1ef);
      camera = new three.PerspectiveCamera(45, 1, 0.001, 10000);
      renderer = new three.WebGLRenderer({ antialias: true });
      renderer.setPixelRatio(window.devicePixelRatio || 1);
      renderer.domElement.style.display = "none";
      viewer.appendChild(renderer.domElement);

      const key = new three.DirectionalLight(0xffffff, 1.2);
      key.position.set(2, -3, 5);
      scene.add(key);
      scene.add(new three.AmbientLight(0xffffff, 0.65));
      grid = new three.GridHelper(2, 16, 0x9aa8a1, 0xd0d7d2);
      grid.rotation.x = Math.PI / 2;
      scene.add(grid);
      axes = new three.AxesHelper(0.35);
      scene.add(axes);

      updateDisplayMode();
      update();
      animate();
    } catch (error) {
      three = null;
      rendererStatus.textContent = "2D canvas editor";
      update();
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
      layers: Math.max(2, Math.floor(number(el.layers))),
      remesh3d: el.remesh3d.checked,
      maxEdge: Math.max(0, number(el.maxEdge)),
      layerSpacing: Math.max(0, number(el.layerSpacing)),
    };
  }

  function update() {
    updateVisibleControls();
    const cfg = readConfig();
    const geom = buildGeometry(cfg);
    const oldKey = currentGeometry ? currentGeometry.key : "";
    currentGeometry = geom;
    stats.textContent = `nodes ${geom.points.length} | elems ${geom.faces.length}`;
    commandBox.textContent = buildCommand(cfg);
    if (geom.key !== oldKey) {
      needs3dFit = true;
      if (keep2dView) {
        view2d.fittedKey = geom.key;
        keep2dView = false;
      } else {
        view2d.fittedKey = "";
      }
    }
    updateDisplayMode();
    if (viewMode === "3d" && three && renderer) {
      renderThree(geom);
    } else {
      renderCanvas2d(geom);
    }
  }

  function updateVisibleControls() {
    const shape = el.shape.value;
    document.querySelectorAll("[data-shape]").forEach((node) => {
      node.style.display = node.dataset.shape.split(" ").includes(shape) ? "grid" : "none";
    });
    el.thickness.disabled = !el.make3d.checked;
    el.layers.disabled = !el.make3d.checked;
    el.remesh3d.disabled = !el.make3d.checked;
    el.maxEdge.disabled = !el.make3d.checked || !el.remesh3d.checked;
    el.layerSpacing.disabled = !el.make3d.checked;
  }

  function updateDisplayMode() {
    mode2dButton.classList.toggle("active", viewMode === "2d");
    mode3dButton.classList.toggle("active", viewMode === "3d");
    viewIsoButton.classList.toggle("subtle", viewMode !== "3d");
    viewTopButton.classList.toggle("subtle", viewMode !== "3d");
    if (renderer) renderer.domElement.style.display = viewMode === "3d" ? "block" : "none";
    canvas.style.display = viewMode === "3d" && renderer ? "none" : "block";
    rendererStatus.textContent = viewMode === "3d" && renderer ? "Three.js 3D preview" : "2D canvas editor";
    viewerHelp.textContent = viewMode === "3d"
      ? "3D: Left drag rotate | Wheel zoom | Right drag pan"
      : "2D: Drag handles to edit | Empty drag pan | Wheel zoom";
    cursorReadout.style.display = viewMode === "2d" ? "block" : "none";
  }

  function setViewMode(mode) {
    viewMode = mode;
    if (mode === "3d") needs3dFit = true;
    updateDisplayMode();
    fitCurrentView(true);
    update();
  }

  function buildGeometry(cfg) {
    const boundary = buildBoundary(cfg);
    const meshBoundary = cfg.make3d && cfg.thickness > 0 && cfg.remesh3d ? remeshBoundary(boundary, cfg) : boundary;
    const meshLayers = cfg.make3d && cfg.thickness > 0 ? effectiveLayers(meshBoundary, cfg) : cfg.layers;
    const points = cfg.make3d && cfg.thickness > 0 ? extrudePoints(meshBoundary, cfg, meshLayers) : boundary;
    const faces = cfg.make3d && cfg.thickness > 0 ? sideWallFaces(meshBoundary.length, meshLayers) : [];
    return {
      boundary,
      meshBoundary,
      meshLayers,
      points,
      faces,
      plane: cfg.plane,
      key: [
        cfg.shape, cfg.radius, cfg.points, cfg.rx, cfg.ry, cfg.width, cfg.height, cfg.naca, cfg.chord,
        cfg.center.join(","), cfg.rotation.join(","), cfg.plane, cfg.scale, cfg.make3d, cfg.thickness, cfg.layers,
        cfg.remesh3d, cfg.maxEdge, cfg.layerSpacing
      ].join("|"),
    };
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

  function remeshBoundary(boundary, cfg) {
    if (boundary.length < 2) return boundary;
    const target = effectiveMaxEdge(boundary, cfg);
    if (!(target > 0)) return boundary;
    const pts = [];
    for (let i = 0; i < boundary.length; i += 1) {
      const a = boundary[i];
      const b = boundary[(i + 1) % boundary.length];
      const length = distance(a, b);
      const pieces = Math.max(1, Math.ceil(length / target - 1e-9));
      for (let j = 0; j < pieces; j += 1) {
        const t = j / pieces;
        pts.push(lerpPoint(a, b, t));
      }
    }
    return pts;
  }

  function effectiveMaxEdge(boundary, cfg) {
    if (cfg.maxEdge > 0) return cfg.maxEdge;
    const lengths = [];
    for (let i = 0; i < boundary.length; i += 1) {
      lengths.push(distance(boundary[i], boundary[(i + 1) % boundary.length]));
    }
    const perimeter = lengths.reduce((sum, value) => sum + value, 0);
    return Math.max(perimeter / 96, 1e-9);
  }

  function effectiveLayers(boundary, cfg) {
    if (cfg.thickness <= 0) return cfg.layers;
    if (cfg.layerSpacing > 0) return Math.max(2, Math.ceil(cfg.thickness / cfg.layerSpacing) + 1);
    if (!cfg.remesh3d) return cfg.layers;
    const autoSpacing = Math.max(effectiveMaxEdge(boundary, cfg) * 3, cfg.thickness / 40, 1e-9);
    return Math.max(cfg.layers, Math.ceil(cfg.thickness / autoSpacing) + 1);
  }

  function extrudePoints(boundary, cfg, layers) {
    const normal = rotatedPlaneNormal(cfg);
    const pts = [];
    for (let layer = 0; layer < layers; layer += 1) {
      const t = layers === 1 ? 0.5 : layer / (layers - 1);
      const d = -cfg.thickness / 2 + t * cfg.thickness;
      boundary.forEach((p) => pts.push(offsetVector(p, normal, d)));
    }
    return pts;
  }

  function sideWallFaces(n, layers) {
    const faces = [];
    for (let layer = 0; layer < layers - 1; layer += 1) {
      const lower = layer * n;
      const upper = (layer + 1) * n;
      for (let a = 0; a < n; a += 1) {
        const b = a === n - 1 ? 0 : a + 1;
        faces.push([lower + a, lower + b, upper + b]);
        faces.push([lower + a, upper + b, upper + a]);
      }
    }
    return faces;
  }

  function renderCanvas2d(geom) {
    const rect = viewer.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.max(1, Math.floor(rect.width * dpr));
    canvas.height = Math.max(1, Math.floor(rect.height * dpr));
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, rect.width, rect.height);
    ctx.fillStyle = "#eef1ef";
    ctx.fillRect(0, 0, rect.width, rect.height);

    const projection = makeProjection(geom.plane);
    const projected = geom.boundary.map(projection);
    fit2dIfNeeded(projected, rect, geom.key);
    drawGrid2d(ctx, rect, geom.plane);
    drawBoundary2d(ctx, projected, rect, geom.plane);
    drawHandles2d(ctx, getEditHandles2d(readConfig()), view2d.hoverHandle);
  }

  function makeProjection(plane) {
    if (plane === "xy") return (p) => [p[0], p[1]];
    if (plane === "xz") return (p) => [p[0], p[2]];
    return (p) => [p[1], p[2]];
  }

  function fit2dIfNeeded(points, rect, key) {
    if (view2d.fittedKey === key) return;
    const b = getBounds2d(points);
    const pad = 60;
    const spanX = Math.max(b.max[0] - b.min[0], 1e-9);
    const spanY = Math.max(b.max[1] - b.min[1], 1e-9);
    view2d.scale = Math.min((rect.width - pad * 2) / spanX, (rect.height - pad * 2) / spanY);
    const center = [(b.min[0] + b.max[0]) / 2, (b.min[1] + b.max[1]) / 2];
    view2d.offset = [
      rect.width / 2 - center[0] * view2d.scale,
      rect.height / 2 + center[1] * view2d.scale,
    ];
    view2d.fittedKey = key;
  }

  function drawGrid2d(ctx, rect, plane) {
    ctx.save();
    const step = niceStep(80 / Math.max(view2d.scale, 1e-9));
    const x0 = screenToWorld2d([0, 0])[0];
    const x1 = screenToWorld2d([rect.width, 0])[0];
    const y0 = screenToWorld2d([0, rect.height])[1];
    const y1 = screenToWorld2d([0, 0])[1];
    ctx.font = "11px Inter, Segoe UI, Arial, sans-serif";
    ctx.fillStyle = "rgba(80,97,90,0.82)";
    ctx.strokeStyle = "rgba(80,97,90,0.13)";
    ctx.lineWidth = 1;
    for (let x = Math.floor(x0 / step) * step; x <= x1; x += step) {
      const sx = worldToScreen2d([x, 0])[0];
      ctx.beginPath();
      ctx.moveTo(sx, 0);
      ctx.lineTo(sx, rect.height);
      ctx.stroke();
      if (sx > 28 && sx < rect.width - 24) ctx.fillText(formatTick(x), sx + 3, rect.height - 34);
    }
    for (let y = Math.floor(y0 / step) * step; y <= y1; y += step) {
      const sy = worldToScreen2d([0, y])[1];
      ctx.beginPath();
      ctx.moveTo(0, sy);
      ctx.lineTo(rect.width, sy);
      ctx.stroke();
      if (sy > 20 && sy < rect.height - 34) ctx.fillText(formatTick(y), 12, sy - 4);
    }
    drawZeroAxes2d(ctx, rect, x0, x1, y0, y1);
    drawMiniAxes2d(ctx, rect, plane);
    ctx.restore();
  }

  function drawZeroAxes2d(ctx, rect, x0, x1, y0, y1) {
    ctx.strokeStyle = "rgba(18,61,51,0.45)";
    ctx.lineWidth = 1.4;
    if (x0 <= 0 && x1 >= 0) {
      const sx = worldToScreen2d([0, 0])[0];
      ctx.beginPath();
      ctx.moveTo(sx, 0);
      ctx.lineTo(sx, rect.height);
      ctx.stroke();
    }
    if (y0 <= 0 && y1 >= 0) {
      const sy = worldToScreen2d([0, 0])[1];
      ctx.beginPath();
      ctx.moveTo(0, sy);
      ctx.lineTo(rect.width, sy);
      ctx.stroke();
    }
  }

  function drawMiniAxes2d(ctx, rect, plane) {
    const labels = planeLabels(plane);
    const x = 28;
    const y = rect.height - 58;
    ctx.strokeStyle = "#215948";
    ctx.fillStyle = "#215948";
    ctx.lineWidth = 1.8;
    drawArrow2d(ctx, x, y, x + 42, y);
    drawArrow2d(ctx, x, y, x, y - 42);
    ctx.font = "12px Inter, Segoe UI, Arial, sans-serif";
    ctx.fillText(labels[0], x + 48, y + 4);
    ctx.fillText(labels[1], x - 4, y - 48);
  }

  function drawBoundary2d(ctx, points, rect, plane) {
    if (!points.length) return;
    ctx.save();
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    ctx.strokeStyle = "#2f7d68";
    ctx.lineWidth = 2.4;
    ctx.beginPath();
    points.forEach((p, i) => {
      const [x, y] = worldToScreen2d(p);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.closePath();
    ctx.stroke();

    const b = getBounds2d(points);
    const c = worldToScreen2d([(b.min[0] + b.max[0]) / 2, (b.min[1] + b.max[1]) / 2]);
    ctx.strokeStyle = "rgba(18,61,51,0.42)";
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.moveTo(c[0] - 7, c[1]);
    ctx.lineTo(c[0] + 7, c[1]);
    ctx.moveTo(c[0], c[1] - 7);
    ctx.lineTo(c[0], c[1] + 7);
    ctx.stroke();

    ctx.fillStyle = "#50615a";
    ctx.font = "12px Inter, Segoe UI, Arial, sans-serif";
    ctx.fillText(`2D ${plane.toUpperCase()} plane`, 16, rect.height - 18);
    ctx.restore();
  }

  function drawHandles2d(ctx, handles, hover) {
    ctx.save();
    handles.forEach((handle) => {
      const [x, y] = worldToScreen2d(handle.pos);
      const active = hover && hover.id === handle.id;
      ctx.beginPath();
      ctx.arc(x, y, active ? 7 : 5.5, 0, Math.PI * 2);
      ctx.fillStyle = handle.kind === "move" ? "#ffffff" : "#2f7d68";
      ctx.strokeStyle = active ? "#0f342b" : "#215948";
      ctx.lineWidth = active ? 2.2 : 1.5;
      ctx.fill();
      ctx.stroke();
      if (active) {
        ctx.fillStyle = "#17211d";
        ctx.font = "12px Inter, Segoe UI, Arial, sans-serif";
        ctx.fillText(handle.label, x + 10, y - 10);
      }
    });
    ctx.restore();
  }

  function worldToScreen2d(p) {
    return [
      p[0] * view2d.scale + view2d.offset[0],
      -p[1] * view2d.scale + view2d.offset[1],
    ];
  }

  function screenToWorld2d(p) {
    return [
      (p[0] - view2d.offset[0]) / view2d.scale,
      -(p[1] - view2d.offset[1]) / view2d.scale,
    ];
  }

  function getEditHandles2d(cfg) {
    const center = projectPointForPlane(cfg.center, cfg.plane);
    const s = Math.max(Math.abs(cfg.scale), 1e-9);
    const handles = [{ id: "move", kind: "move", label: "Move", pos: center }];
    if (cfg.shape === "circle") {
      handles.push({ id: "radius", kind: "size", label: "Radius", pos: [center[0] + cfg.radius * s, center[1]] });
    } else if (cfg.shape === "ellipse") {
      handles.push({ id: "rx", kind: "size", label: "Rx", pos: [center[0] + cfg.rx * s, center[1]] });
      handles.push({ id: "ry", kind: "size", label: "Ry", pos: [center[0], center[1] + cfg.ry * s] });
    } else if (cfg.shape === "rectangle") {
      handles.push({ id: "width", kind: "size", label: "Width", pos: [center[0] + cfg.width * s / 2, center[1]] });
      handles.push({ id: "height", kind: "size", label: "Height", pos: [center[0], center[1] + cfg.height * s / 2] });
    } else if (cfg.shape === "naca") {
      handles.push({ id: "chord", kind: "size", label: "Chord", pos: [center[0] + cfg.chord * s / 2, center[1]] });
    }
    return handles;
  }

  function hitHandle2d(screenPoint) {
    const handles = getEditHandles2d(readConfig());
    let best = null;
    let bestDistance = Infinity;
    handles.forEach((handle) => {
      const p = worldToScreen2d(handle.pos);
      const d = Math.hypot(screenPoint[0] - p[0], screenPoint[1] - p[1]);
      if (d < bestDistance) {
        bestDistance = d;
        best = handle;
      }
    });
    return bestDistance <= 12 ? best : null;
  }

  function applyHandleDrag2d(world) {
    const cfg = readConfig();
    const handle = view2d.activeHandle;
    if (!handle) return;
    if (handle.id === "move") {
      const du = world[0] - view2d.startWorld[0];
      const dv = world[1] - view2d.startWorld[1];
      setCenterFromPlane(cfg.plane, [
        view2d.startCenter[0],
        view2d.startCenter[1],
        view2d.startCenter[2],
      ], du, dv);
    } else {
      const center = projectPointForPlane(cfg.center, cfg.plane);
      const s = Math.max(Math.abs(cfg.scale), 1e-9);
      if (handle.id === "radius") setNumberValue(el.radius, Math.max(1e-6, Math.hypot(world[0] - center[0], world[1] - center[1]) / s));
      if (handle.id === "rx") setNumberValue(el.rx, Math.max(1e-6, Math.abs(world[0] - center[0]) / s));
      if (handle.id === "ry") setNumberValue(el.ry, Math.max(1e-6, Math.abs(world[1] - center[1]) / s));
      if (handle.id === "width") setNumberValue(el.width, Math.max(1e-6, 2 * Math.abs(world[0] - center[0]) / s));
      if (handle.id === "height") setNumberValue(el.height, Math.max(1e-6, 2 * Math.abs(world[1] - center[1]) / s));
      if (handle.id === "chord") setNumberValue(el.chord, Math.max(1e-6, 2 * Math.abs(world[0] - center[0]) / s));
    }
    keep2dView = true;
    update();
  }

  function renderThree(geom) {
    const rect = viewer.getBoundingClientRect();
    renderer.setSize(rect.width, rect.height);
    camera.aspect = rect.width / Math.max(1, rect.height);
    camera.updateProjectionMatrix();
    if (objectGroup) scene.remove(objectGroup);
    objectGroup = new three.Group();

    if (geom.faces.length) {
      const g = new three.BufferGeometry();
      g.setAttribute("position", new three.Float32BufferAttribute(geom.points.flat(), 3));
      g.setIndex(geom.faces.flat());
      g.computeVertexNormals();
      const mesh = new three.Mesh(
        g,
        new three.MeshStandardMaterial({ color: 0x2f7d68, side: three.DoubleSide, roughness: 0.6, metalness: 0.02, transparent: true, opacity: 0.72 })
      );
      const edges = new three.LineSegments(
        new three.EdgesGeometry(g, 18),
        new three.LineBasicMaterial({ color: 0x123d33, transparent: true, opacity: 0.45 })
      );
      objectGroup.add(mesh, edges);
    } else {
      const g = new three.BufferGeometry();
      g.setAttribute("position", new three.Float32BufferAttribute(geom.points.flat(), 3));
      const loop = new three.LineLoop(g, new three.LineBasicMaterial({ color: 0x2f7d68 }));
      objectGroup.add(loop);
    }

    scene.add(objectGroup);
    if (needs3dFit) fit3dView(true);
    needsFrame = true;
  }

  function animate() {
    requestAnimationFrame(animate);
    if (!renderer || !camera || !needsFrame || viewMode !== "3d") return;
    applyCamera();
    renderer.render(scene, camera);
    needsFrame = false;
  }

  function fitCurrentView(force) {
    if (viewMode === "3d") {
      fit3dView(force);
      return;
    }
    view2d.fittedKey = "";
    if (currentGeometry) renderCanvas2d(currentGeometry);
  }

  function fit3dView(force) {
    if (!currentGeometry || !currentGeometry.points.length) return;
    const b = getBounds(currentGeometry.points);
    const center = [(b.min[0] + b.max[0]) / 2, (b.min[1] + b.max[1]) / 2, (b.min[2] + b.max[2]) / 2];
    const span = Math.max(b.max[0] - b.min[0], b.max[1] - b.min[1], b.max[2] - b.min[2], 1e-4);
    const newDistance = span * 2.4;
    if (force || needs3dFit) {
      orbit.target = center;
      orbit.distance = newDistance;
      updateHelpers(span, center);
      needs3dFit = false;
      needsFrame = true;
    }
  }

  function updateHelpers(span, center) {
    if (!grid || !axes) return;
    grid.scale.setScalar(Math.max(span, 1e-4));
    grid.position.set(center[0], center[1], center[2]);
    axes.scale.setScalar(Math.max(span * 0.35, 1e-4));
    axes.position.set(center[0], center[1], center[2]);
  }

  function applyCamera() {
    const pitch = clamp(orbit.pitch, -Math.PI / 2 + 0.02, Math.PI / 2 - 0.02);
    const cp = Math.cos(pitch);
    const pos = [
      orbit.target[0] + orbit.distance * cp * Math.cos(orbit.yaw),
      orbit.target[1] + orbit.distance * cp * Math.sin(orbit.yaw),
      orbit.target[2] + orbit.distance * Math.sin(pitch),
    ];
    camera.position.set(pos[0], pos[1], pos[2]);
    camera.lookAt(orbit.target[0], orbit.target[1], orbit.target[2]);
    camera.near = Math.max(orbit.distance / 500, 1e-6);
    camera.far = Math.max(orbit.distance * 500, 10);
    camera.updateProjectionMatrix();
  }

  function setPresetView(mode) {
    if (viewMode !== "3d") {
      fitCurrentView(true);
      return;
    }
    if (mode === "top") {
      orbit.yaw = -Math.PI / 2;
      orbit.pitch = Math.PI / 2 - 0.02;
    } else {
      orbit.yaw = -0.72;
      orbit.pitch = 0.62;
    }
    fit3dView(true);
  }

  function onPointerDown(event) {
    if (viewMode === "2d") {
      const screen = localPointer(event);
      const world = screenToWorld2d(screen);
      const handle = hitHandle2d(screen);
      view2d.dragging = true;
      view2d.action = handle ? "handle" : "pan";
      view2d.activeHandle = handle;
      view2d.startWorld = world;
      view2d.startCenter = readConfig().center.slice();
      view2d.x = event.clientX;
      view2d.y = event.clientY;
      viewer.setPointerCapture(event.pointerId);
      return;
    }
    if (!three) return;
    orbit.dragging = true;
    orbit.button = event.button;
    orbit.x = event.clientX;
    orbit.y = event.clientY;
    viewer.setPointerCapture(event.pointerId);
  }

  function onPointerMove(event) {
    if (viewMode === "2d") {
      updateCursorReadout(event);
      if (!view2d.dragging) {
        view2d.hoverHandle = hitHandle2d(localPointer(event));
        viewer.style.cursor = view2d.hoverHandle ? "crosshair" : "grab";
        if (currentGeometry) renderCanvas2d(currentGeometry);
        return;
      }
      if (view2d.action === "handle") {
        applyHandleDrag2d(screenToWorld2d(localPointer(event)));
        return;
      }
      const dx = event.clientX - view2d.x;
      const dy = event.clientY - view2d.y;
      view2d.x = event.clientX;
      view2d.y = event.clientY;
      view2d.offset[0] += dx;
      view2d.offset[1] += dy;
      if (currentGeometry) renderCanvas2d(currentGeometry);
      return;
    }
    if (!orbit.dragging || !three) return;
    const dx = event.clientX - orbit.x;
    const dy = event.clientY - orbit.y;
    orbit.x = event.clientX;
    orbit.y = event.clientY;
    if (orbit.button === 2 || orbit.button === 1) {
      panCamera(dx, dy);
    } else {
      orbit.yaw -= dx * 0.006;
      orbit.pitch += dy * 0.006;
      orbit.pitch = clamp(orbit.pitch, -Math.PI / 2 + 0.02, Math.PI / 2 - 0.02);
    }
    needsFrame = true;
  }

  function onPointerUp(event) {
    view2d.dragging = false;
    view2d.action = "pan";
    view2d.activeHandle = null;
    orbit.dragging = false;
    try {
      viewer.releasePointerCapture(event.pointerId);
    } catch (_) {
      // Pointer capture may already be released by the browser.
    }
  }

  function onWheel(event) {
    event.preventDefault();
    if (viewMode === "2d") {
      const screen = localPointer(event);
      const before = screenToWorld2d(screen);
      const factor = Math.exp(-event.deltaY * 0.001);
      view2d.scale = clamp(view2d.scale * factor, 1e-9, 1e9);
      const after = worldToScreen2d(before);
      view2d.offset[0] += screen[0] - after[0];
      view2d.offset[1] += screen[1] - after[1];
      if (currentGeometry) renderCanvas2d(currentGeometry);
      updateCursorReadout(event);
      return;
    }
    if (!three) return;
    const factor = Math.exp(event.deltaY * 0.001);
    orbit.distance = clamp(orbit.distance * factor, 1e-5, 1e6);
    needsFrame = true;
  }

  function panCamera(dx, dy) {
    const scale = orbit.distance * 0.0012;
    const right = [Math.sin(orbit.yaw), -Math.cos(orbit.yaw), 0];
    const up = [
      -Math.cos(orbit.yaw) * Math.sin(orbit.pitch),
      -Math.sin(orbit.yaw) * Math.sin(orbit.pitch),
      Math.cos(orbit.pitch),
    ];
    for (let i = 0; i < 3; i += 1) {
      orbit.target[i] += (-dx * right[i] + dy * up[i]) * scale;
    }
  }

  function localPointer(event) {
    const rect = viewer.getBoundingClientRect();
    return [event.clientX - rect.left, event.clientY - rect.top];
  }

  function updateCursorReadout(event) {
    const world = screenToWorld2d(localPointer(event));
    const labels = planeLabels(readConfig().plane);
    cursorReadout.textContent = `${labels[0]}=${formatTick(world[0])}, ${labels[1]}=${formatTick(world[1])}`;
  }

  function projectPointForPlane(point, plane) {
    if (plane === "xy") return [point[0], point[1]];
    if (plane === "xz") return [point[0], point[2]];
    return [point[1], point[2]];
  }

  function setCenterFromPlane(plane, startCenter, du, dv) {
    if (plane === "xy") {
      setNumberValue(el.centerX, startCenter[0] + du);
      setNumberValue(el.centerY, startCenter[1] + dv);
    } else if (plane === "xz") {
      setNumberValue(el.centerX, startCenter[0] + du);
      setNumberValue(el.centerZ, startCenter[2] + dv);
    } else {
      setNumberValue(el.centerY, startCenter[1] + du);
      setNumberValue(el.centerZ, startCenter[2] + dv);
    }
  }

  function setNumberValue(input, value) {
    input.value = formatInputNumber(value);
  }

  function planeLabels(plane) {
    if (plane === "xy") return ["x", "y"];
    if (plane === "xz") return ["x", "z"];
    return ["y", "z"];
  }

  function drawArrow2d(ctx, x0, y0, x1, y1) {
    const angle = Math.atan2(y1 - y0, x1 - x0);
    ctx.beginPath();
    ctx.moveTo(x0, y0);
    ctx.lineTo(x1, y1);
    ctx.lineTo(x1 - 8 * Math.cos(angle - 0.45), y1 - 8 * Math.sin(angle - 0.45));
    ctx.moveTo(x1, y1);
    ctx.lineTo(x1 - 8 * Math.cos(angle + 0.45), y1 - 8 * Math.sin(angle + 0.45));
    ctx.stroke();
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
    const lines = ["solid surface_editor"];
    geom.faces.forEach((f) => {
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
    const s = cfg.scale;
    if (cfg.shape === "circle") params.push(`--param radius=${cfg.radius * s}`, `--param n=${cfg.points}`);
    if (cfg.shape === "ellipse") params.push(`--param rx=${cfg.rx * s}`, `--param ry=${cfg.ry * s}`, `--param n=${cfg.points}`);
    if (cfg.shape === "rectangle") params.push(`--param width=${cfg.width * s}`, `--param height=${cfg.height * s}`);
    if (cfg.shape === "naca") params.push(`--param code=${cfg.naca}`, `--param chord=${cfg.chord * s}`, `--param n=${cfg.points}`);
    const parts = [
      "python geometry/unstructure_surface/run_surface_tools.py",
      "--case-dir path/to/case",
      "generate",
      cfg.shape,
      ...params,
      "--center", 0, 0, 0,
      "--plane", cfg.plane,
    ];
    if (cfg.make3d) parts.push("--param", `layers=${cfg.layers}`, "--thickness", cfg.thickness);
    if (cfg.make3d && cfg.remesh3d) parts.push("--param", `max_edge=${cfg.maxEdge}`);
    if (cfg.make3d && cfg.remesh3d) parts.push("--param", `layer_spacing=${cfg.layerSpacing}`);
    if (cfg.rotation.some((v) => v !== 0)) parts.push("--rotate", ...cfg.rotation);
    if (cfg.center.some((v) => v !== 0)) parts.push("--translate", ...cfg.center);
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

  function rotatedPlaneNormal(cfg) {
    let normal;
    if (cfg.plane === "xy") normal = [0, 0, 1];
    else if (cfg.plane === "xz") normal = [0, 1, 0];
    else normal = [1, 0, 0];
    return rotateVector(normal, cfg.rotation);
  }

  function number(input) {
    return Number(input.value || 0);
  }

  function offsetVector(p, direction, d) {
    return [
      p[0] + direction[0] * d,
      p[1] + direction[1] * d,
      p[2] + direction[2] * d,
    ];
  }

  function rotateVector(p, rotation) {
    const [rx, ry, rz] = rotation.map((v) => v * Math.PI / 180);
    return rotateZ(rotateY(rotateX(p, rx), ry), rz);
  }

  function distance(a, b) {
    return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
  }

  function lerpPoint(a, b, t) {
    return [
      a[0] + (b[0] - a[0]) * t,
      a[1] + (b[1] - a[1]) * t,
      a[2] + (b[2] - a[2]) * t,
    ];
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

  function getBounds2d(points) {
    const min = [Infinity, Infinity];
    const max = [-Infinity, -Infinity];
    points.forEach((p) => {
      min[0] = Math.min(min[0], p[0]);
      min[1] = Math.min(min[1], p[1]);
      max[0] = Math.max(max[0], p[0]);
      max[1] = Math.max(max[1], p[1]);
    });
    return { min, max };
  }

  function niceStep(raw) {
    const power = 10 ** Math.floor(Math.log10(raw || 1));
    const unit = raw / power;
    if (unit < 2) return power;
    if (unit < 5) return 2 * power;
    return 5 * power;
  }

  function formatTick(value) {
    const abs = Math.abs(value);
    if (abs >= 1000 || (abs > 0 && abs < 0.001)) return value.toExponential(2);
    if (abs >= 100) return value.toFixed(1).replace(/\.0$/, "");
    if (abs >= 10) return value.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
    return value.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
  }

  function formatInputNumber(value) {
    return Number(value.toPrecision(12)).toString();
  }

  function normal(a, b, c) {
    const u = [b[0] - a[0], b[1] - a[1], b[2] - a[2]];
    const v = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
    const n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]];
    const len = Math.hypot(n[0], n[1], n[2]) || 1;
    return [n[0] / len, n[1] / len, n[2] / len];
  }

  function clamp(value, lo, hi) {
    return Math.min(hi, Math.max(lo, value));
  }

  function pad(value, width) {
    return String(value).padStart(width, " ");
  }
}());
