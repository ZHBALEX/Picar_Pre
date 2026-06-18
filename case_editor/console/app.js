(function () {
  const MAX_SURFACE_POINTS = 35000;
  const MAX_SURFACE_TRIANGLES = 9000;
  const MAX_GRID_LINES = 28;

  const el = {
    caseDir: document.getElementById("caseDir"),
    loadCase: document.getElementById("loadCase"),
    fitView: document.getElementById("fitView"),
    topView: document.getElementById("topView"),
    isoView: document.getElementById("isoView"),
    dropzone: document.getElementById("dropzone"),
    fileInput: document.getElementById("fileInput"),
    viewport: document.getElementById("viewport"),
    stats: document.getElementById("stats"),
    subtitle: document.getElementById("subtitle"),
    commands: document.getElementById("commands"),
    showSurfacePoints: document.getElementById("showSurfacePoints"),
    showSurfaceLines: document.getElementById("showSurfaceLines"),
    showMeshBounds: document.getElementById("showMeshBounds"),
    showDenseRegion: document.getElementById("showDenseRegion"),
    showFullMesh: document.getElementById("showFullMesh"),
    showAxes: document.getElementById("showAxes"),
  };

  const state = {
    surface: null,
    mesh: { x: null, y: null, z: null, denseBox: null },
    bounds: null,
    angleX: -0.55,
    angleY: 0.72,
    zoom: 1,
    panX: 0,
    panY: 0,
    dragging: false,
    lastX: 0,
    lastY: 0,
    framePending: false,
  };

  init();

  function init() {
    const params = new URLSearchParams(location.search);
    el.caseDir.value = params.get("case_dir") || "";
    el.loadCase.addEventListener("click", loadCase);
    el.fitView.addEventListener("click", fit);
    el.topView.addEventListener("click", topView);
    el.isoView.addEventListener("click", isoView);
    el.fileInput.addEventListener("change", () => readFiles(el.fileInput.files));
    ["dragenter", "dragover"].forEach((name) => el.dropzone.addEventListener(name, onDrag));
    ["dragleave", "drop"].forEach((name) => el.dropzone.addEventListener(name, offDrag));
    el.dropzone.addEventListener("drop", (event) => readFiles(event.dataTransfer.files));
    [
      el.showSurfacePoints,
      el.showSurfaceLines,
      el.showMeshBounds,
      el.showDenseRegion,
      el.showFullMesh,
      el.showAxes,
    ].forEach((node) => node.addEventListener("change", requestDraw));
    el.viewport.addEventListener("mousedown", startDrag);
    window.addEventListener("mousemove", drag);
    window.addEventListener("mouseup", () => { state.dragging = false; });
    el.viewport.addEventListener("wheel", zoom, { passive: false });
    window.addEventListener("resize", requestDraw);
    updateCommands();
    loadCase();
    requestDraw();
  }

  async function loadCase() {
    const caseDir = el.caseDir.value.trim();
    setStatus("Loading case files...");
    try {
      const query = caseDir ? `?case_dir=${encodeURIComponent(caseDir)}` : "";
      const report = await fetchJson(`/api/report${query}`);
      el.caseDir.value = report.case_dir || caseDir;
      const loadedQuery = `?case_dir=${encodeURIComponent(el.caseDir.value.trim())}`;
      const loads = [];

      state.surface = null;
      state.mesh = { x: null, y: null, z: null, denseBox: null };

      if (report.surface) {
        loads.push(fetchText(`/api/surface${loadedQuery}`).then((text) => {
          state.surface = parseSurface(text);
        }));
      }
      if (report.mesh) {
        state.mesh.denseBox = report.mesh.dense_box || null;
        ["x", "y", "z"].forEach((axis) => {
          loads.push(fetchText(`/api/grid${loadedQuery}&axis=${axis}`)
            .then((text) => { state.mesh[axis] = parseGridAxis(text); })
            .catch(() => { state.mesh[axis] = null; }));
        });
      }

      await Promise.all(loads);
      recomputeBounds();
      fit();
      setStatus(formatReport(report));
    } catch (err) {
      setStatus(String(err));
    }
    updateCommands();
  }

  async function readFiles(files) {
    for (const file of Array.from(files)) {
      const text = await file.text();
      const lower = file.name.toLowerCase();
      if (lower.includes("unstruc_surface")) {
        state.surface = parseSurface(text);
      } else if (lower.startsWith("xgrid")) {
        state.mesh.x = parseGridAxis(text);
      } else if (lower.startsWith("ygrid")) {
        state.mesh.y = parseGridAxis(text);
      } else if (lower.startsWith("zgrid")) {
        state.mesh.z = parseGridAxis(text);
      }
    }
    recomputeBounds();
    fit();
    updateStats();
  }

  function parseSurface(text) {
    const values = numericTokens(text);
    const bodies = [];
    let i = 0;
    while (i < values.length) {
      while (i + 2 < values.length && isSentinel(values, i)) i += 3;
      if (i >= values.length) break;
      const nodeCount = Math.trunc(values[i]);
      const elemCount = Math.trunc(values[i + 1]);
      i += 2;
      const points = new Float64Array(nodeCount * 3);
      for (let n = 0; n < nodeCount; n += 1) {
        i += 1;
        points[n * 3] = values[i++];
        points[n * 3 + 1] = values[i++];
        points[n * 3 + 2] = values[i++];
      }
      const elems = new Int32Array(elemCount * 3);
      for (let e = 0; e < elemCount; e += 1) {
        i += 1;
        elems[e * 3] = Math.trunc(values[i++]) - 1;
        elems[e * 3 + 1] = Math.trunc(values[i++]) - 1;
        elems[e * 3 + 2] = Math.trunc(values[i++]) - 1;
      }
      if (i + 2 < values.length && !isSentinel(values, i)) i += 3;
      bodies.push({ points, elems, nodeCount, elemCount });
    }
    return { bodies };
  }

  function parseGridAxis(text) {
    const values = [];
    text.split(/\r?\n/).forEach((line) => {
      const parts = line.trim().split(/\s+/).filter(Boolean);
      if (parts.length === 1) values.push(Number(parts[0]));
      if (parts.length >= 2) values.push(Number(parts[1]));
    });
    return Float64Array.from(values.filter(Number.isFinite));
  }

  function numericTokens(text) {
    const matches = text.match(/[+-]?(?:\d+\.?\d*|\.\d+)(?:[eEdD][+-]?\d+)?/g) || [];
    const values = new Float64Array(matches.length);
    for (let i = 0; i < matches.length; i += 1) values[i] = Number(matches[i].replace(/[dD]/, "E"));
    return values;
  }

  function requestDraw() {
    if (state.framePending) return;
    state.framePending = true;
    requestAnimationFrame(() => {
      state.framePending = false;
      draw();
    });
  }

  function draw() {
    const canvas = el.viewport;
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.max(1, Math.floor(rect.width * dpr));
    canvas.height = Math.max(1, Math.floor(rect.height * dpr));
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, rect.width, rect.height);
    ctx.fillStyle = "#f7f8f9";
    ctx.fillRect(0, 0, rect.width, rect.height);

    if (!state.bounds) {
      empty(ctx, rect, "Load a case or drop surface/grid files");
      return;
    }

    if (el.showAxes.checked) drawAxesAndTicks(ctx, rect);
    if (el.showMeshBounds.checked) drawMeshBounds(ctx, rect);
    if (el.showDenseRegion.checked) drawDenseRegion(ctx, rect);
    if (el.showFullMesh.checked) drawSampledGrid(ctx, rect);
    drawSurface(ctx, rect);
  }

  function drawSurface(ctx, rect) {
    const surface = state.surface;
    if (!surface || !surface.bodies.length) return;
    surface.bodies.forEach((body, bodyIndex) => {
      const color = bodyIndex % 2 ? "#7a5a2f" : "#0e5f95";
      const pointStride = Math.max(1, Math.ceil(body.nodeCount / MAX_SURFACE_POINTS));
      const triStride = Math.max(1, Math.ceil(body.elemCount / MAX_SURFACE_TRIANGLES));
      if (el.showSurfaceLines.checked && body.elemCount) {
        ctx.strokeStyle = "rgba(20, 54, 82, 0.38)";
        ctx.lineWidth = 0.55;
        for (let e = 0; e < body.elemCount; e += triStride) {
          pathTriangle(ctx, rect, body, e);
        }
      }
      if (el.showSurfacePoints.checked) {
        ctx.fillStyle = color;
        for (let i = 0; i < body.nodeCount; i += pointStride) {
          const p = projectPoint(rect, body.points[i * 3], body.points[i * 3 + 1], body.points[i * 3 + 2]);
          ctx.fillRect(p.x - 1.1, p.y - 1.1, 2.2, 2.2);
        }
      }
    });
  }

  function drawMeshBounds(ctx, rect) {
    const box = meshDomainBox();
    if (!box) return;
    drawBoxFaces(ctx, rect, box, "rgba(95, 100, 105, 0.12)");
    drawBoxEdges(ctx, rect, box, "#33383d", 1.6);
  }

  function drawDenseRegion(ctx, rect) {
    const dense = state.mesh.denseBox || inferDenseBox();
    if (!dense) return;
    const zFallback = state.mesh.z && state.mesh.z.length ? [state.mesh.z[0], state.mesh.z[state.mesh.z.length - 1]] : [0, 0];
    const z0 = dense.z0 === dense.z1 ? zFallback[0] : dense.z0;
    const z1 = dense.z0 === dense.z1 ? zFallback[1] : dense.z1;
    const box = { x0: dense.x0, x1: dense.x1, y0: dense.y0, y1: dense.y1, z0, z1 };
    drawBoxFaces(ctx, rect, box, "rgba(42, 132, 122, 0.18)");
    drawBoxEdges(ctx, rect, box, "#1a786f", 1.4);
  }

  function drawSampledGrid(ctx, rect) {
    const { x, y, z } = state.mesh;
    if (!x || !y) return;
    const xs = sample(x, MAX_GRID_LINES);
    const ys = sample(y, MAX_GRID_LINES);
    const zs = z && z.length ? sample(z, Math.min(18, MAX_GRID_LINES)) : [0];
    ctx.strokeStyle = "rgba(47, 127, 193, 0.22)";
    ctx.lineWidth = 0.5;
    ys.forEach((yy) => zs.forEach((zz) => linePoints(ctx, rect, [x[0], yy, zz], [x[x.length - 1], yy, zz])));
    xs.forEach((xx) => zs.forEach((zz) => linePoints(ctx, rect, [xx, y[0], zz], [xx, y[y.length - 1], zz])));
    if (z && z.length) {
      xs.forEach((xx) => ys.forEach((yy) => linePoints(ctx, rect, [xx, yy, z[0]], [xx, yy, z[z.length - 1]])));
    }
  }

  function drawAxesAndTicks(ctx, rect) {
    const b = state.bounds;
    const box = { x0: b.min[0], x1: b.max[0], y0: b.min[1], y1: b.max[1], z0: b.min[2], z1: b.max[2] };
    drawBoxEdges(ctx, rect, box, "rgba(120, 130, 140, 0.26)", 0.8);
    drawFloorGrid(ctx, rect, box);
    drawAxis(ctx, rect, [box.x0, box.y0, box.z0], [box.x1, box.y0, box.z0], "X Axis", ticks(box.x0, box.x1), 0);
    drawAxis(ctx, rect, [box.x0, box.y0, box.z0], [box.x0, box.y1, box.z0], "Y Axis", ticks(box.y0, box.y1), 1);
    drawAxis(ctx, rect, [box.x0, box.y0, box.z0], [box.x0, box.y0, box.z1], "Z Axis", ticks(box.z0, box.z1), 2);
  }

  function drawFloorGrid(ctx, rect, box) {
    ctx.strokeStyle = "rgba(160, 166, 172, 0.26)";
    ctx.lineWidth = 0.7;
    ticks(box.x0, box.x1).forEach((x) => linePoints(ctx, rect, [x, box.y0, box.z0], [x, box.y1, box.z0]));
    ticks(box.y0, box.y1).forEach((y) => linePoints(ctx, rect, [box.x0, y, box.z0], [box.x1, y, box.z0]));
    ticks(box.z0, box.z1).forEach((z) => {
      linePoints(ctx, rect, [box.x0, box.y0, z], [box.x1, box.y0, z]);
      linePoints(ctx, rect, [box.x0, box.y0, z], [box.x0, box.y1, z]);
    });
  }

  function drawAxis(ctx, rect, start, end, label, tickValues, axisIndex) {
    ctx.strokeStyle = "#22282e";
    ctx.fillStyle = "#22282e";
    ctx.lineWidth = 1.5;
    linePoints(ctx, rect, start, end);
    const end2 = projectPoint(rect, end[0], end[1], end[2]);
    ctx.font = "15px Segoe UI, Arial";
    ctx.fillText(label, end2.x + 8, end2.y - 8);
    ctx.font = "12px Segoe UI, Arial";
    tickValues.forEach((value) => {
      const p = start.slice();
      p[axisIndex] = value;
      const pp = projectPoint(rect, p[0], p[1], p[2]);
      ctx.fillRect(pp.x - 2, pp.y - 2, 4, 4);
      ctx.fillText(formatTick(value), pp.x + 5, pp.y + 14);
    });
  }

  function pathTriangle(ctx, rect, body, elemIndex) {
    const a = body.elems[elemIndex * 3];
    const b = body.elems[elemIndex * 3 + 1];
    const c = body.elems[elemIndex * 3 + 2];
    const pa = projectBodyPoint(rect, body, a);
    const pb = projectBodyPoint(rect, body, b);
    const pc = projectBodyPoint(rect, body, c);
    ctx.beginPath();
    ctx.moveTo(pa.x, pa.y);
    ctx.lineTo(pb.x, pb.y);
    ctx.lineTo(pc.x, pc.y);
    ctx.closePath();
    ctx.stroke();
  }

  function projectBodyPoint(rect, body, index) {
    return projectPoint(rect, body.points[index * 3], body.points[index * 3 + 1], body.points[index * 3 + 2]);
  }

  function drawBoxFaces(ctx, rect, box, fillStyle) {
    const faces = [
      [[box.x0, box.y0, box.z0], [box.x1, box.y0, box.z0], [box.x1, box.y1, box.z0], [box.x0, box.y1, box.z0]],
      [[box.x0, box.y0, box.z1], [box.x1, box.y0, box.z1], [box.x1, box.y1, box.z1], [box.x0, box.y1, box.z1]],
      [[box.x0, box.y0, box.z0], [box.x1, box.y0, box.z0], [box.x1, box.y0, box.z1], [box.x0, box.y0, box.z1]],
      [[box.x1, box.y0, box.z0], [box.x1, box.y1, box.z0], [box.x1, box.y1, box.z1], [box.x1, box.y0, box.z1]],
      [[box.x0, box.y1, box.z0], [box.x1, box.y1, box.z0], [box.x1, box.y1, box.z1], [box.x0, box.y1, box.z1]],
      [[box.x0, box.y0, box.z0], [box.x0, box.y1, box.z0], [box.x0, box.y1, box.z1], [box.x0, box.y0, box.z1]],
    ];
    ctx.fillStyle = fillStyle;
    faces.forEach((face) => {
      const first = projectPoint(rect, face[0][0], face[0][1], face[0][2]);
      ctx.beginPath();
      ctx.moveTo(first.x, first.y);
      face.slice(1).forEach((point) => {
        const p = projectPoint(rect, point[0], point[1], point[2]);
        ctx.lineTo(p.x, p.y);
      });
      ctx.closePath();
      ctx.fill();
    });
  }

  function drawBoxEdges(ctx, rect, box, color, width) {
    const corners = [
      [box.x0, box.y0, box.z0], [box.x1, box.y0, box.z0], [box.x1, box.y1, box.z0], [box.x0, box.y1, box.z0],
      [box.x0, box.y0, box.z1], [box.x1, box.y0, box.z1], [box.x1, box.y1, box.z1], [box.x0, box.y1, box.z1],
    ];
    const edges = [[0, 1], [1, 2], [2, 3], [3, 0], [4, 5], [5, 6], [6, 7], [7, 4], [0, 4], [1, 5], [2, 6], [3, 7]];
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    edges.forEach(([a, b]) => linePoints(ctx, rect, corners[a], corners[b]));
  }

  function linePoints(ctx, rect, a, b) {
    const pa = projectPoint(rect, a[0], a[1], a[2]);
    const pb = projectPoint(rect, b[0], b[1], b[2]);
    ctx.beginPath();
    ctx.moveTo(pa.x, pa.y);
    ctx.lineTo(pb.x, pb.y);
    ctx.stroke();
  }

  function projectPoint(rect, x, y, z) {
    const b = state.bounds || { min: [-1, -1, -1], max: [1, 1, 1], span: 2 };
    const cx = (b.min[0] + b.max[0]) / 2;
    const cy = (b.min[1] + b.max[1]) / 2;
    const cz = (b.min[2] + b.max[2]) / 2;
    const px = x - cx;
    const py = y - cy;
    const pz = z - cz;
    const cosy = Math.cos(state.angleY);
    const siny = Math.sin(state.angleY);
    const cosx = Math.cos(state.angleX);
    const sinx = Math.sin(state.angleX);
    const rx = px * cosy + pz * siny;
    const rz = -px * siny + pz * cosy;
    const ry = py * cosx - rz * sinx;
    const scale = 0.78 * Math.min(rect.width, rect.height) / Math.max(b.span, 1e-12) * state.zoom;
    return {
      x: rect.width / 2 + state.panX + rx * scale,
      y: rect.height / 2 + state.panY - ry * scale,
    };
  }

  function recomputeBounds() {
    const min = [Infinity, Infinity, Infinity];
    const max = [-Infinity, -Infinity, -Infinity];
    const add = (x, y, z) => {
      min[0] = Math.min(min[0], x); min[1] = Math.min(min[1], y); min[2] = Math.min(min[2], z);
      max[0] = Math.max(max[0], x); max[1] = Math.max(max[1], y); max[2] = Math.max(max[2], z);
    };
    if (state.surface) {
      state.surface.bodies.forEach((body) => {
        for (let i = 0; i < body.nodeCount; i += 1) add(body.points[i * 3], body.points[i * 3 + 1], body.points[i * 3 + 2]);
      });
    }
    const box = meshDomainBox();
    if (box) {
      add(box.x0, box.y0, box.z0);
      add(box.x1, box.y1, box.z1);
    }
    if (!Number.isFinite(min[0])) {
      state.bounds = null;
      return;
    }
    for (let i = 0; i < 3; i += 1) {
      if (Math.abs(max[i] - min[i]) < 1e-12) {
        min[i] -= 0.5;
        max[i] += 0.5;
      }
    }
    state.bounds = { min, max, span: Math.max(max[0] - min[0], max[1] - min[1], max[2] - min[2]) };
  }

  function meshDomainBox() {
    const { x, y, z } = state.mesh;
    if (!x || !y || x.length === 0 || y.length === 0) return null;
    const z0 = z && z.length ? z[0] : 0;
    const z1 = z && z.length ? z[z.length - 1] : 0;
    return { x0: x[0], x1: x[x.length - 1], y0: y[0], y1: y[y.length - 1], z0, z1 };
  }

  function inferDenseBox() {
    if (!state.mesh.x || !state.mesh.y) return null;
    const xr = inferDenseRange(state.mesh.x);
    const yr = inferDenseRange(state.mesh.y);
    if (!xr || !yr) return null;
    const zr = state.mesh.z && state.mesh.z.length > 2 ? inferDenseRange(state.mesh.z) : null;
    return {
      x0: xr[0],
      x1: xr[1],
      y0: yr[0],
      y1: yr[1],
      z0: zr ? zr[0] : 0,
      z1: zr ? zr[1] : 0,
    };
  }

  function inferDenseRange(values) {
    if (!values || values.length < 2) return null;
    const spacing = [];
    for (let i = 0; i < values.length - 1; i += 1) {
      const delta = values[i + 1] - values[i];
      if (delta > 0 && Number.isFinite(delta)) spacing.push(delta);
    }
    if (!spacing.length) return null;
    const minSpacing = Math.min(...spacing);
    const maxSpacing = Math.max(...spacing);
    if (maxSpacing / minSpacing < 1.05) return [values[0], values[values.length - 1]];
    const threshold = minSpacing * 1.08;
    let bestStart = 0;
    let bestEnd = 0;
    let start = -1;
    for (let i = 0; i < values.length - 1; i += 1) {
      const isDense = values[i + 1] - values[i] <= threshold;
      if (isDense && start < 0) start = i;
      if ((!isDense || i === values.length - 2) && start >= 0) {
        const end = isDense && i === values.length - 2 ? i + 1 : i;
        if (end - start > bestEnd - bestStart) {
          bestStart = start;
          bestEnd = end;
        }
        start = -1;
      }
    }
    return [values[bestStart], values[Math.min(bestEnd + 1, values.length - 1)]];
  }

  function sample(values, maxCount) {
    if (!values || values.length <= maxCount) return values || [];
    const step = Math.max(1, Math.ceil(values.length / maxCount));
    const out = [];
    for (let i = 0; i < values.length; i += step) out.push(values[i]);
    if (out[out.length - 1] !== values[values.length - 1]) out.push(values[values.length - 1]);
    return out;
  }

  function ticks(min, max) {
    if (!Number.isFinite(min) || !Number.isFinite(max)) return [];
    const span = max - min;
    if (Math.abs(span) < 1e-12) return [min];
    const step = niceStep(span / 4);
    const start = Math.ceil(min / step) * step;
    const values = [];
    for (let value = start; value <= max + step * 0.5 && values.length < 7; value += step) values.push(value);
    return values;
  }

  function niceStep(raw) {
    const power = 10 ** Math.floor(Math.log10(Math.max(raw, 1e-12)));
    const unit = raw / power;
    if (unit <= 1) return power;
    if (unit <= 2) return 2 * power;
    if (unit <= 5) return 5 * power;
    return 10 * power;
  }

  function formatTick(value) {
    return Math.abs(value) >= 100 || Math.abs(value) < 0.01 ? value.toExponential(1) : Number(value.toPrecision(4)).toString();
  }

  function fit() {
    state.zoom = 1;
    state.panX = 0;
    state.panY = 0;
    requestDraw();
  }

  function topView() {
    state.angleX = -1.5708;
    state.angleY = 0;
    requestDraw();
  }

  function isoView() {
    state.angleX = -0.55;
    state.angleY = 0.72;
    requestDraw();
  }

  function startDrag(event) {
    state.dragging = true;
    state.lastX = event.clientX;
    state.lastY = event.clientY;
  }

  function drag(event) {
    if (!state.dragging) return;
    const dx = event.clientX - state.lastX;
    const dy = event.clientY - state.lastY;
    state.angleY += dx * 0.008;
    state.angleX += dy * 0.008;
    state.lastX = event.clientX;
    state.lastY = event.clientY;
    requestDraw();
  }

  function zoom(event) {
    event.preventDefault();
    state.zoom *= event.deltaY < 0 ? 1.12 : 0.89;
    state.zoom = Math.max(0.05, Math.min(80, state.zoom));
    requestDraw();
  }

  function updateStats() {
    const lines = [];
    if (state.surface) {
      const nodes = state.surface.bodies.reduce((sum, body) => sum + body.nodeCount, 0);
      const elems = state.surface.bodies.reduce((sum, body) => sum + body.elemCount, 0);
      lines.push(`surface bodies: ${state.surface.bodies.length}`);
      lines.push(`surface nodes : ${nodes}`);
      lines.push(`surface elems : ${elems}`);
    }
    if (state.mesh.x && state.mesh.y) {
      lines.push(`mesh x/y/z    : ${state.mesh.x.length} / ${state.mesh.y.length} / ${state.mesh.z ? state.mesh.z.length : 0}`);
      lines.push(`dense region  : ${state.mesh.denseBox ? "available" : "not found in mesh input"}`);
    }
    setStatus(lines.join("\n") || "ready");
  }

  function empty(ctx, rect, text) {
    ctx.fillStyle = "#66737f";
    ctx.font = "14px Segoe UI, Arial";
    ctx.textAlign = "center";
    ctx.fillText(text, rect.width / 2, rect.height / 2);
  }

  function onDrag(event) {
    event.preventDefault();
    el.dropzone.classList.add("dragging");
  }

  function offDrag(event) {
    event.preventDefault();
    el.dropzone.classList.remove("dragging");
  }

  function isSentinel(values, i) {
    return values[i] < -5 && values[i + 1] < -5 && values[i + 2] < -5;
  }

  function setStatus(text) {
    el.stats.textContent = text;
    el.subtitle.textContent = text.split("\n")[0] || "ready";
  }

  function formatReport(report) {
    const lines = [`case: ${report.case_dir}`];
    if (report.surface) lines.push(`surface bodies: ${report.surface.bodies.length}`);
    if (report.mesh) lines.push(`mesh axes: ${report.mesh.axes.map((a) => `${a.axis}:${a.count}`).join(" ")}`);
    lines.push(`dense region: ${report.mesh && report.mesh.dense_box ? "available" : "not found"}`);
    lines.push(`validation: ${report.validation.length ? "FAIL" : "PASS"}`);
    report.validation.forEach((item) => lines.push(`- ${item}`));
    return lines.join("\n");
  }

  function updateCommands() {
    const caseDir = el.caseDir.value || "path/to/case";
    el.commands.textContent = [
      `python case_editor/run_case_editor.py --case-dir "${caseDir}" report`,
      `python -m mesh.run_mesh_tools --case-dir "${caseDir}" inspect`,
      `python geometry/unstructure_surface/run_surface_tools.py --case-dir "${caseDir}" inspect --roundtrip`,
    ].join("\n\n");
  }

  async function fetchText(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(await res.text());
    return res.text();
  }

  async function fetchJson(url) {
    return JSON.parse(await fetchText(url));
  }
}());
