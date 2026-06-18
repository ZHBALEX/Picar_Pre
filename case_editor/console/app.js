(function () {
  const MAX_SURFACE_POINTS = 35000;
  const MAX_SURFACE_TRIANGLES = 9000;
  const MAX_GRID_LINES = 28;
  const MESH_INPUT_NAME = "mesh_input_twolayers.dat";

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
    geometryFile: document.getElementById("geometryFile"),
    importGeometry: document.getElementById("importGeometry"),
    appendGeometry: document.getElementById("appendGeometry"),
    exportStl: document.getElementById("exportStl"),
    meshAxes: document.getElementById("meshAxes"),
    scaleRef: document.getElementById("scaleRef"),
    relax: document.getElementById("relax"),
    previewMesh: document.getElementById("previewMesh"),
    saveMeshInput: document.getElementById("saveMeshInput"),
    generateMesh: document.getElementById("generateMesh"),
  };

  const state = {
    surface: null,
    mesh: { x: null, y: null, z: null, denseBox: null },
    meshControlsReady: false,
    meshPreviewSuspended: false,
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
    postApiAvailable: false,
  };

  init();

  function init() {
    const params = new URLSearchParams(location.search);
    el.caseDir.value = params.get("case_dir") || "";
    buildMeshControls();
    fillMeshControls(defaultMeshParams());
    state.meshControlsReady = true;
    document.querySelectorAll("[data-panel]").forEach((button) => {
      button.addEventListener("click", () => selectPanel(button.dataset.panel));
    });
    el.loadCase.addEventListener("click", loadCase);
    el.fitView.addEventListener("click", fit);
    el.topView.addEventListener("click", topView);
    el.isoView.addEventListener("click", isoView);
    el.fileInput.addEventListener("change", () => readFiles(el.fileInput.files));
    el.geometryFile.addEventListener("change", () => previewGeometrySelection());
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
    el.importGeometry.addEventListener("click", () => importGeometry(false));
    el.appendGeometry.addEventListener("click", () => importGeometry(true));
    el.exportStl.addEventListener("click", exportStl);
    el.previewMesh.addEventListener("click", previewMeshFromControls);
    el.saveMeshInput.addEventListener("click", saveMeshInput);
    el.generateMesh.addEventListener("click", generateMesh);
    el.scaleRef.addEventListener("input", previewMeshFromControls);
    el.relax.addEventListener("input", previewMeshFromControls);
    window.addEventListener("resize", requestDraw);
    updateCommands();
    checkServerCapabilities().then(loadCase);
    requestDraw();
  }

  async function checkServerCapabilities() {
    try {
      const health = await fetchJson("/api/health");
      state.postApiAvailable = Boolean(health.post_api);
      if (!state.postApiAvailable) {
        setStatus("This console server is old. Restart: Ctrl+C, then python -B picar_console.py");
      }
    } catch (err) {
      state.postApiAvailable = false;
      setStatus("Could not verify console API. Restart: Ctrl+C, then python -B picar_console.py");
    }
    setWriteButtonsEnabled(state.postApiAvailable);
  }

  function setWriteButtonsEnabled(enabled) {
    [el.saveMeshInput, el.generateMesh, el.importGeometry, el.appendGeometry, el.exportStl].forEach((button) => {
      button.disabled = !enabled;
      button.title = enabled ? "" : "Restart the Python console server to enable file writes.";
    });
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
      await loadMeshInputControls();
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
      const lower = file.name.toLowerCase();
      if (lower.includes("unstruc_surface")) {
        const text = await file.text();
        state.surface = parseSurface(text);
      } else if (lower.endsWith(".stl")) {
        state.surface = await parseStlFile(file);
        setStatus(`STL preview loaded: ${file.name}`);
      } else if (isMeshInputName(lower)) {
        const params = parseMeshInputText(await file.text());
        fillMeshControls(params);
        state.meshControlsReady = true;
        previewMeshFromControls();
        setStatus(`Mesh input loaded: ${file.name}`);
      } else if (lower.startsWith("xgrid")) {
        const text = await file.text();
        state.mesh.x = parseGridAxis(text);
      } else if (lower.startsWith("ygrid")) {
        const text = await file.text();
        state.mesh.y = parseGridAxis(text);
      } else if (lower.startsWith("zgrid")) {
        const text = await file.text();
        state.mesh.z = parseGridAxis(text);
      }
    }
    updateMeshControlsFromImportedGrid();
    recomputeBounds();
    fit();
    updateStats();
  }

  async function previewGeometrySelection() {
    const file = el.geometryFile.files && el.geometryFile.files[0];
    if (!file) return;
    const lower = file.name.toLowerCase();
    try {
      if (lower.endsWith(".stl")) {
        state.surface = await parseStlFile(file);
      } else if (lower.endsWith(".dat")) {
        state.surface = parseSurface(await file.text());
      } else {
        setStatus("Geometry preview supports .stl and .dat.");
        return;
      }
      recomputeBounds();
      fit();
      updateStats();
      setStatus(`Geometry preview loaded: ${file.name}`);
    } catch (err) {
      setStatus(`Geometry preview failed: ${err.message || err}`);
    }
  }

  async function loadMeshInputControls() {
    try {
      const query = `?case_dir=${encodeURIComponent(el.caseDir.value.trim())}`;
      const payload = await fetchJson(`/api/mesh-input${query}`);
      fillMeshControls(payload.params);
      state.meshControlsReady = true;
      previewMeshFromControls();
    } catch (err) {
      state.meshControlsReady = true;
      fillMeshControls(defaultMeshParams());
      setStatus(`Mesh input controls not loaded: ${err}`);
    }
  }

  function selectPanel(panelId) {
    document.querySelectorAll("[data-panel]").forEach((button) => {
      button.classList.toggle("active", button.dataset.panel === panelId);
    });
    document.querySelectorAll(".control-panel").forEach((panel) => {
      panel.classList.toggle("active", panel.id === panelId);
    });
    if (panelId === "meshPanel" && !meshControlsHaveValues()) {
      loadMeshInputControls();
    }
  }

  function buildMeshControls() {
    const defs = [
      ["x", "X Axis", "left", "right", "x"],
      ["y", "Y Axis", "bottom", "top", "y"],
      ["z", "Z Axis", "front", "back", "z"],
    ];
    el.meshAxes.innerHTML = `
      <div class="axis-tabs">
        <button class="active" data-axis-tab="x" type="button">X</button>
        <button data-axis-tab="y" type="button">Y</button>
        <button data-axis-tab="z" type="button">Z</button>
      </div>
      ${defs.map(([axis, title, lowName, highName]) => `
      <section class="axis-group" data-axis="${axis}">
        <h3>${title}</h3>
        <div class="grid four">
          <label>Start<input id="${axis}Start" type="number" step="0.01"></label>
          <label>Dense start<input id="${axis}DenseStart" type="number" step="0.01"></label>
          <label>Dense end<input id="${axis}DenseEnd" type="number" step="0.01"></label>
          <label>End<input id="${axis}End" type="number" step="0.01"></label>
        </div>
        <div class="grid four">
          <label>${lowName} stretch<input id="${axis}LeftStretch" type="number" min="0" step="1"></label>
          <label>${lowName} layer<input id="${axis}LeftUniform" type="number" min="0" step="1"></label>
          <label>Dense count<input id="${axis}DenseCount" type="number" min="0" step="1"></label>
          <label>${highName} layer<input id="${axis}RightUniform" type="number" min="0" step="1"></label>
        </div>
        <div class="grid four">
          <label>${highName} stretch<input id="${axis}RightStretch" type="number" min="0" step="1"></label>
          <label>${lowName} length<input id="${axis}LeftLayerLength" type="number" min="0" step="0.01"></label>
          <label>${highName} length<input id="${axis}RightLayerLength" type="number" min="0" step="0.01"></label>
          <label>Ratio<input id="${axis}Ratio" type="number" min="0.0001" step="0.01"></label>
        </div>
      </section>
    `).join("")}`;
    el.meshAxes.querySelectorAll("[data-axis-tab]").forEach((button) => {
      button.addEventListener("click", () => selectAxisTab(button.dataset.axisTab));
    });
    el.meshAxes.querySelectorAll("input").forEach((input) => input.addEventListener("input", previewMeshFromControls));
    selectAxisTab("x");
  }

  function fillMeshControls(params) {
    state.meshPreviewSuspended = true;
    const p = params || {};
    const xStart = state.mesh.x && state.mesh.x.length ? state.mesh.x[0] : 0;
    const yStart = state.mesh.y && state.mesh.y.length ? state.mesh.y[0] : 0;
    const zStart = state.mesh.z && state.mesh.z.length ? state.mesh.z[0] : 0;
    el.scaleRef.value = p.scale_ref ?? 1;
    el.relax.value = p.relax ?? 0.001;
    fillAxis("x", {
      start: xStart,
      denseStart: xStart + (p.x_center_dense ?? 12) - 0.5 * (p.Lx_dense ?? 8),
      denseEnd: xStart + (p.x_center_dense ?? 12) + 0.5 * (p.Lx_dense ?? 8),
      end: xStart + (p.Lx ?? 24),
      leftStretch: p.n_left_stretch ?? 16,
      leftUniform: p.n_left_uniform ?? 8,
      denseCount: p.Nx_dense ?? 64,
      rightUniform: p.n_right_uniform ?? 8,
      rightStretch: p.n_right_stretch ?? 16,
      leftLayerLength: p.len_left ?? 1,
      rightLayerLength: p.len_right ?? 1,
      ratio: p.r_left ?? p.r_right ?? 1.08,
    });
    fillAxis("y", {
      start: yStart,
      denseStart: yStart + (p.y_center_dense ?? 10) - 0.5 * (p.Ly_dense ?? 6),
      denseEnd: yStart + (p.y_center_dense ?? 10) + 0.5 * (p.Ly_dense ?? 6),
      end: yStart + (p.Ly ?? 20),
      leftStretch: p.n_bottom_stretch ?? 16,
      leftUniform: p.n_bottom_uniform ?? 8,
      denseCount: p.Ny_dense ?? 48,
      rightUniform: p.n_top_uniform ?? 8,
      rightStretch: p.n_top_stretch ?? 16,
      leftLayerLength: p.len_bottom ?? 1,
      rightLayerLength: p.len_top ?? 1,
      ratio: p.r_bottom ?? p.r_top ?? 1.06,
    });
    fillAxis("z", {
      start: zStart,
      denseStart: zStart + (p.z_center_dense ?? 0) - 0.5 * (p.Lz_dense ?? 0),
      denseEnd: zStart + (p.z_center_dense ?? 0) + 0.5 * (p.Lz_dense ?? 0),
      end: zStart + (p.Lz ?? 0),
      leftStretch: p.n_front_stretch ?? 0,
      leftUniform: p.n_front_uniform ?? 0,
      denseCount: p.Nz_dense ?? 0,
      rightUniform: p.n_back_uniform ?? 0,
      rightStretch: p.n_back_stretch ?? 0,
      leftLayerLength: p.len_front ?? 0,
      rightLayerLength: p.len_back ?? 0,
      ratio: p.r_front ?? p.r_back ?? 1,
    });
    state.meshPreviewSuspended = false;
  }

  function selectAxisTab(axis) {
    el.meshAxes.querySelectorAll("[data-axis-tab]").forEach((button) => {
      button.classList.toggle("active", button.dataset.axisTab === axis);
    });
    el.meshAxes.querySelectorAll(".axis-group").forEach((group) => {
      group.classList.toggle("active", group.dataset.axis === axis);
    });
  }

  function fillAxis(axis, values) {
    const map = {
      Start: values.start,
      DenseStart: values.denseStart,
      DenseEnd: values.denseEnd,
      End: values.end,
      LeftStretch: values.leftStretch,
      LeftUniform: values.leftUniform,
      DenseCount: values.denseCount,
      RightUniform: values.rightUniform,
      RightStretch: values.rightStretch,
      LeftLayerLength: values.leftLayerLength,
      RightLayerLength: values.rightLayerLength,
      Ratio: values.ratio,
    };
    Object.entries(map).forEach(([suffix, value]) => {
      const input = document.getElementById(axis + suffix);
      if (input) input.value = formatControlNumber(value);
    });
  }

  function readMeshParams(options = {}) {
    const validate = options.validate !== false;
    const x = readAxisControls("x");
    const y = readAxisControls("y");
    const z = readAxisControls("z");
    if (validate) {
      validateAxisControls("x", x);
      validateAxisControls("y", y);
      if (z.end > z.start || z.denseCount > 0) validateAxisControls("z", z, true);
    }
    return {
      scale_ref: numValue(el.scaleRef, 1),
      Lx: x.end - x.start,
      Ly: y.end - y.start,
      Lz: Math.max(0, z.end - z.start),
      x_center_dense: 0.5 * (x.denseStart + x.denseEnd) - x.start,
      y_center_dense: 0.5 * (y.denseStart + y.denseEnd) - y.start,
      z_center_dense: Math.max(0, 0.5 * (z.denseStart + z.denseEnd) - z.start),
      Lx_dense: x.denseEnd - x.denseStart,
      Ly_dense: y.denseEnd - y.denseStart,
      Lz_dense: Math.max(0, z.denseEnd - z.denseStart),
      Nx_dense: x.denseCount,
      Ny_dense: y.denseCount,
      Nz_dense: z.denseCount,
      len_left: x.leftLayerLength,
      len_right: x.rightLayerLength,
      len_bottom: y.leftLayerLength,
      len_top: y.rightLayerLength,
      len_front: z.leftLayerLength,
      len_back: z.rightLayerLength,
      n_left_stretch: x.leftStretch,
      n_left_uniform: x.leftUniform,
      n_right_uniform: x.rightUniform,
      n_right_stretch: x.rightStretch,
      n_bottom_stretch: y.leftStretch,
      n_bottom_uniform: y.leftUniform,
      n_top_uniform: y.rightUniform,
      n_top_stretch: y.rightStretch,
      n_front_stretch: z.leftStretch,
      n_front_uniform: z.leftUniform,
      n_back_uniform: z.rightUniform,
      n_back_stretch: z.rightStretch,
      r_left: x.ratio,
      r_right: x.ratio,
      r_bottom: y.ratio,
      r_top: y.ratio,
      r_front: z.ratio,
      r_back: z.ratio,
      relax: numValue(el.relax, 0.001),
      flag_plot: false,
      flag_preplot: false,
    };
  }

  function readAxisControls(axis) {
    return {
      start: numId(axis + "Start"),
      denseStart: numId(axis + "DenseStart"),
      denseEnd: numId(axis + "DenseEnd"),
      end: numId(axis + "End"),
      leftStretch: intId(axis + "LeftStretch"),
      leftUniform: intId(axis + "LeftUniform"),
      denseCount: intId(axis + "DenseCount"),
      rightUniform: intId(axis + "RightUniform"),
      rightStretch: intId(axis + "RightStretch"),
      leftLayerLength: numId(axis + "LeftLayerLength"),
      rightLayerLength: numId(axis + "RightLayerLength"),
      ratio: Math.max(1e-8, numId(axis + "Ratio")),
    };
  }

  function previewMeshFromControls() {
    if (state.meshPreviewSuspended || !state.meshControlsReady || !meshControlsHaveValues()) return;
    try {
      const params = readMeshParams();
      const x = readAxisControls("x");
      const y = readAxisControls("y");
      const z = readAxisControls("z");
      state.mesh.x = makeAxisNodesFromControls("x");
      state.mesh.y = makeAxisNodesFromControls("y");
      state.mesh.z = z.end > z.start ? makeAxisNodesFromControls("z") : null;
      state.mesh.denseBox = {
        x0: x.denseStart,
        x1: x.denseEnd,
        y0: y.denseStart,
        y1: y.denseEnd,
        z0: z.denseStart,
        z1: z.denseEnd,
      };
      recomputeBounds();
      updateStats();
      requestDraw();
    } catch (err) {
      setStatus(`Mesh preview error: ${err.message || err}`);
    }
  }

  function validateAxisControls(axis, cfg, allowFlat = false) {
    if (!Number.isFinite(cfg.start) || !Number.isFinite(cfg.end)) throw new Error(`${axis.toUpperCase()} range is incomplete`);
    if (allowFlat && cfg.end === cfg.start && cfg.denseCount === 0) return;
    if (!(cfg.end > cfg.start)) throw new Error(`${axis.toUpperCase()} end must be greater than start`);
    if (!(cfg.denseStart >= cfg.start && cfg.denseEnd <= cfg.end && cfg.denseEnd >= cfg.denseStart)) {
      throw new Error(`${axis.toUpperCase()} dense range must stay inside the axis range`);
    }
  }

  function meshControlsHaveValues() {
    return ["xStart", "xDenseStart", "xDenseEnd", "xEnd", "yStart", "yDenseStart", "yDenseEnd", "yEnd"]
      .every((id) => {
        const input = document.getElementById(id);
        return input && String(input.value).trim() !== "";
      });
  }

  function defaultMeshParams() {
    return {
      scale_ref: 1,
      relax: 0.001,
      Lx: 24,
      Ly: 20,
      Lz: 0,
      x_center_dense: 12,
      y_center_dense: 10,
      z_center_dense: 0,
      Lx_dense: 8,
      Ly_dense: 6,
      Lz_dense: 0,
      Nx_dense: 64,
      Ny_dense: 48,
      Nz_dense: 0,
      n_left_stretch: 16,
      n_left_uniform: 8,
      n_right_uniform: 8,
      n_right_stretch: 16,
      n_bottom_stretch: 16,
      n_bottom_uniform: 8,
      n_top_uniform: 8,
      n_top_stretch: 16,
      n_front_stretch: 0,
      n_front_uniform: 0,
      n_back_uniform: 0,
      n_back_stretch: 0,
      len_left: 1,
      len_right: 1,
      len_bottom: 1,
      len_top: 1,
      len_front: 0,
      len_back: 0,
      r_left: 1.08,
      r_right: 1.08,
      r_bottom: 1.06,
      r_top: 1.06,
      r_front: 1,
      r_back: 1,
    };
  }

  function makeAxisNodesFromControls(axis) {
    const cfg = readAxisControls(axis);
    if (cfg.end <= cfg.start) return Float64Array.from([cfg.start, cfg.end]);
    const sizes = [
      ...geometricSizes(Math.max(0, cfg.denseStart - cfg.start - cfg.leftLayerLength), cfg.leftStretch, cfg.ratio).reverse(),
      ...geometricSizes(Math.max(0, cfg.leftLayerLength), cfg.leftUniform, 1),
      ...geometricSizes(Math.max(0, cfg.denseEnd - cfg.denseStart), cfg.denseCount, 1),
      ...geometricSizes(Math.max(0, cfg.rightLayerLength), cfg.rightUniform, 1),
      ...geometricSizes(Math.max(0, cfg.end - cfg.denseEnd - cfg.rightLayerLength), cfg.rightStretch, cfg.ratio),
    ];
    const nodes = [cfg.start];
    sizes.forEach((size) => nodes.push(nodes[nodes.length - 1] + size));
    if (nodes.length === 1) nodes.push(cfg.end);
    nodes[nodes.length - 1] = cfg.end;
    return Float64Array.from(nodes);
  }

  function geometricSizes(length, count, ratio) {
    if (count <= 0 || length <= 0) return [];
    if (Math.abs(ratio - 1) < 1e-12) return Array(count).fill(length / count);
    const first = length * (1 - ratio) / (1 - ratio ** count);
    return Array.from({ length: count }, (_, i) => first * ratio ** i);
  }

  async function saveMeshInput() {
    try {
      await postJson("/api/mesh/save", { case_dir: el.caseDir.value.trim(), input_name: MESH_INPUT_NAME, params: readMeshParams({ validate: false }) });
      setStatus(`${MESH_INPUT_NAME} saved. Use Generate XYZ to check whether it can produce grid files.`);
      await loadCase();
    } catch (err) {
      setStatus(`Save input failed: ${err.message || err}`);
    }
  }

  async function generateMesh() {
    try {
      const result = await postJson("/api/mesh/generate", { case_dir: el.caseDir.value.trim(), input_name: MESH_INPUT_NAME, params: readMeshParams() });
      if (result.mesh) {
        state.mesh.x = Float64Array.from(result.mesh.x);
        state.mesh.y = Float64Array.from(result.mesh.y);
        state.mesh.z = result.mesh.z.length ? Float64Array.from(result.mesh.z) : null;
      }
      recomputeBounds();
      requestDraw();
      setStatus("xgrid/ygrid/zgrid generated.");
    } catch (err) {
      setStatus(`Generate XYZ failed: ${err.message || err}`);
    }
  }

  async function importGeometry(append) {
    const file = el.geometryFile.files && el.geometryFile.files[0];
    if (!file) {
      setStatus("Choose a .stl or .dat file first.");
      return;
    }
    try {
      setStatus(`Importing geometry: ${file.name}`);
      const lower = file.name.toLowerCase();
      if (lower.endsWith(".dat")) {
        const content = await file.text();
        await postJson("/api/geometry/save-surface", { case_dir: el.caseDir.value.trim(), content });
      } else if (lower.endsWith(".stl")) {
        const contentBase64 = await fileToBase64(file);
        await postJson("/api/geometry/import-stl", {
          case_dir: el.caseDir.value.trim(),
          filename: file.name,
          content_base64: contentBase64,
          append,
        });
      } else {
        setStatus("Geometry import supports .stl and .dat.");
        return;
      }
      await loadCase();
      setStatus(append ? "Geometry appended." : "Geometry imported.");
    } catch (err) {
      setStatus(`Geometry import failed: ${err.message || err}`);
    }
  }

  async function exportStl() {
    try {
      const result = await postJson("/api/geometry/export-stl", { case_dir: el.caseDir.value.trim(), output: "surface_export.stl" });
      setStatus(`STL exported: ${result.path}`);
    } catch (err) {
      setStatus(`STL export failed: ${err.message || err}`);
    }
  }

  function fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result).split(",", 2)[1] || "");
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
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

  async function parseStlFile(file) {
    const buffer = await file.arrayBuffer();
    const bytes = new Uint8Array(buffer);
    if (looksLikeBinaryStl(bytes)) return parseBinaryStl(bytes);
    const text = new TextDecoder("utf-8").decode(bytes);
    return parseAsciiStl(text);
  }

  function looksLikeBinaryStl(bytes) {
    if (bytes.length < 84) return false;
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const triangles = view.getUint32(80, true);
    return 84 + triangles * 50 === bytes.length;
  }

  function parseBinaryStl(bytes) {
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const triangles = view.getUint32(80, true);
    const points = new Float64Array(triangles * 9);
    const elems = new Int32Array(triangles * 3);
    let offset = 84;
    for (let tri = 0; tri < triangles; tri += 1) {
      offset += 12;
      for (let corner = 0; corner < 3; corner += 1) {
        const idx = tri * 9 + corner * 3;
        points[idx] = view.getFloat32(offset, true);
        points[idx + 1] = view.getFloat32(offset + 4, true);
        points[idx + 2] = view.getFloat32(offset + 8, true);
        elems[tri * 3 + corner] = tri * 3 + corner;
        offset += 12;
      }
      offset += 2;
    }
    return { bodies: [{ points, elems, nodeCount: triangles * 3, elemCount: triangles }] };
  }

  function parseAsciiStl(text) {
    const matches = Array.from(text.matchAll(/vertex\s+([+-]?(?:\d+\.?\d*|\.\d+)(?:[eEdD][+-]?\d+)?)\s+([+-]?(?:\d+\.?\d*|\.\d+)(?:[eEdD][+-]?\d+)?)\s+([+-]?(?:\d+\.?\d*|\.\d+)(?:[eEdD][+-]?\d+)?)/gi));
    if (matches.length < 3 || matches.length % 3 !== 0) throw new Error("Could not parse STL vertices");
    const points = new Float64Array(matches.length * 3);
    const elems = new Int32Array(matches.length);
    matches.forEach((match, i) => {
      points[i * 3] = Number(match[1].replace(/[dD]/, "E"));
      points[i * 3 + 1] = Number(match[2].replace(/[dD]/, "E"));
      points[i * 3 + 2] = Number(match[3].replace(/[dD]/, "E"));
      elems[i] = i;
    });
    return { bodies: [{ points, elems, nodeCount: matches.length, elemCount: matches.length / 3 }] };
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

  function isMeshInputName(lowerName) {
    return lowerName.includes("mesh_input") || lowerName.includes("input_mesh") || lowerName === MESH_INPUT_NAME;
  }

  function parseMeshInputText(text) {
    const values = [];
    text.split(/\r?\n/).forEach((raw) => {
      const line = raw.split("!", 1)[0].trim();
      if (!line) return;
      const parts = line.split(/\s+/);
      if (parts.length === 1) values.push(parseMeshScalar(parts[0]));
    });
    if (values.length >= 40) return meshParamsFromValues(values, false);
    if (values.length >= 28) return meshParamsFromValues(values, true);
    throw new Error(`Mesh input has ${values.length} scalar values; expected at least 28.`);
  }

  function parseMeshScalar(value) {
    const lowered = value.toLowerCase();
    if (["t", "true", ".true."].includes(lowered)) return true;
    if (["f", "false", ".false."].includes(lowered)) return false;
    const number = Number(value.replace(/[dD]/, "E"));
    return Number.isFinite(number) ? number : value;
  }

  function meshParamsFromValues(values, twolayer2d) {
    if (!twolayer2d) {
      const keys = [
        "scale_ref", "Lx", "Ly", "Lz", "x_center_dense", "y_center_dense", "z_center_dense",
        "Lx_dense", "Ly_dense", "Lz_dense", "Nx_dense", "Ny_dense", "Nz_dense",
        "len_left", "len_right", "len_bottom", "len_top", "len_front", "len_back",
        "n_left_stretch", "n_left_uniform", "n_right_uniform", "n_right_stretch",
        "n_bottom_stretch", "n_bottom_uniform", "n_top_uniform", "n_top_stretch",
        "n_front_stretch", "n_front_uniform", "n_back_uniform", "n_back_stretch",
        "r_left", "r_right", "r_bottom", "r_top", "r_front", "r_back", "relax", "flag_plot", "flag_preplot",
      ];
      return Object.fromEntries(keys.map((key, i) => [key, values[i]]));
    }
    const p = defaultMeshParams();
    [
      p.scale_ref, p.Lx, p.Ly, p.x_center_dense, p.y_center_dense, p.Lx_dense, p.Ly_dense,
      p.Nx_dense, p.Ny_dense, p.len_left, p.len_right, p.len_bottom, p.len_top,
      p.n_left_stretch, p.n_left_uniform, p.n_right_uniform, p.n_right_stretch,
      p.n_bottom_stretch, p.n_bottom_uniform, p.n_top_uniform, p.n_top_stretch,
      p.r_left, p.r_right, p.r_bottom, p.r_top, p.relax, p.flag_plot, p.flag_preplot,
    ] = values.slice(0, 28);
    p.Lz = 0;
    p.Lz_dense = 0;
    p.Nz_dense = 0;
    return p;
  }

  function updateMeshControlsFromImportedGrid() {
    if (!state.mesh.x || !state.mesh.y) return;
    const params = paramsFromCurrentGrid();
    fillMeshControls(params);
    state.meshControlsReady = true;
  }

  function paramsFromCurrentGrid() {
    const x = axisParamsFromValues(state.mesh.x, "x");
    const y = axisParamsFromValues(state.mesh.y, "y");
    const z = state.mesh.z && state.mesh.z.length > 1 ? axisParamsFromValues(state.mesh.z, "z") : null;
    const p = defaultMeshParams();
    Object.assign(p, {
      Lx: x.length,
      Ly: y.length,
      Lz: z ? z.length : 0,
      x_center_dense: x.center,
      y_center_dense: y.center,
      z_center_dense: z ? z.center : 0,
      Lx_dense: x.denseLength,
      Ly_dense: y.denseLength,
      Lz_dense: z ? z.denseLength : 0,
      Nx_dense: x.denseCount,
      Ny_dense: y.denseCount,
      Nz_dense: z ? z.denseCount : 0,
      n_left_stretch: x.leftStretch,
      n_left_uniform: x.leftUniform,
      n_right_uniform: x.rightUniform,
      n_right_stretch: x.rightStretch,
      n_bottom_stretch: y.leftStretch,
      n_bottom_uniform: y.leftUniform,
      n_top_uniform: y.rightUniform,
      n_top_stretch: y.rightStretch,
      n_front_stretch: z ? z.leftStretch : 0,
      n_front_uniform: z ? z.leftUniform : 0,
      n_back_uniform: z ? z.rightUniform : 0,
      n_back_stretch: z ? z.rightStretch : 0,
      len_left: x.leftLayer,
      len_right: x.rightLayer,
      len_bottom: y.leftLayer,
      len_top: y.rightLayer,
      len_front: z ? z.leftLayer : 0,
      len_back: z ? z.rightLayer : 0,
    });
    return p;
  }

  function axisParamsFromValues(values) {
    const start = values[0];
    const end = values[values.length - 1];
    const length = end - start;
    const spacing = [];
    for (let i = 0; i < values.length - 1; i += 1) spacing.push(values[i + 1] - values[i]);
    const minSpacing = Math.min(...spacing.filter((v) => v > 0));
    const denseMask = spacing.map((v) => v <= minSpacing * 1.08);
    let bestStart = 0;
    let bestEnd = spacing.length - 1;
    let runStart = -1;
    for (let i = 0; i < denseMask.length; i += 1) {
      if (denseMask[i] && runStart < 0) runStart = i;
      if ((!denseMask[i] || i === denseMask.length - 1) && runStart >= 0) {
        const runEnd = denseMask[i] && i === denseMask.length - 1 ? i : i - 1;
        if (runEnd - runStart > bestEnd - bestStart || bestEnd === spacing.length - 1) {
          bestStart = runStart;
          bestEnd = runEnd;
        }
        runStart = -1;
      }
    }
    const denseStart = values[bestStart] ?? start;
    const denseEnd = values[Math.min(bestEnd + 1, values.length - 1)] ?? end;
    const leftIntervals = bestStart;
    const rightIntervals = Math.max(0, spacing.length - bestEnd - 1);
    return {
      length,
      center: 0.5 * (denseStart + denseEnd) - start,
      denseLength: Math.max(0, denseEnd - denseStart),
      denseCount: Math.max(1, bestEnd - bestStart + 1),
      leftStretch: leftIntervals,
      leftUniform: 0,
      rightUniform: 0,
      rightStretch: rightIntervals,
      leftLayer: 0,
      rightLayer: 0,
    };
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

  function numId(id, fallback = 0) {
    return numValue(document.getElementById(id), fallback);
  }

  function intId(id, fallback = 0) {
    return Math.max(0, Math.floor(numId(id, fallback)));
  }

  function numValue(input, fallback = 0) {
    const value = Number(input && input.value);
    return Number.isFinite(value) ? value : fallback;
  }

  function formatControlNumber(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return "0";
    return Number(number.toPrecision(10)).toString();
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

  async function postJson(url, payload) {
    if (!state.postApiAvailable) {
      throw new Error("Console write API is not available. Restart the server: Ctrl+C, then python -B picar_console.py");
    }
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const text = await res.text();
    let data = {};
    try {
      data = text ? JSON.parse(text) : {};
    } catch (err) {
      const snippet = text.trim().slice(0, 120).replace(/\s+/g, " ");
      throw new Error(`Console server returned HTML/text instead of JSON. Restart the server. Response: ${snippet}`);
    }
    if (!res.ok || data.ok === false) throw new Error(data.error || text || res.statusText);
    return data;
  }
}());
