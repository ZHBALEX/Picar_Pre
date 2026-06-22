(function () {
  const MAX_SURFACE_POINTS = 35000;
  const MAX_SURFACE_TRIANGLES = 80000;
  const INTERACTIVE_SURFACE_TRIANGLES = 12000;
  const MAX_GRID_LINES = 28;
  const DENSE_UNIFORM_RATIO = 1.05;
  const MESH_INPUT_FIELDS = [
    ["scale_ref", "float"], ["Lx", "float"], ["Ly", "float"], ["Lz", "float"],
    ["x_center_dense", "float"], ["y_center_dense", "float"], ["z_center_dense", "float"],
    ["Lx_dense", "float"], ["Ly_dense", "float"], ["Lz_dense", "float"],
    ["Nx_dense", "int"], ["Ny_dense", "int"], ["Nz_dense", "int"],
    ["len_left", "float"], ["len_right", "float"], ["len_bottom", "float"], ["len_top", "float"], ["len_front", "float"], ["len_back", "float"],
    ["n_left_stretch", "int"], ["n_left_uniform", "int"], ["n_right_uniform", "int"], ["n_right_stretch", "int"],
    ["n_bottom_stretch", "int"], ["n_bottom_uniform", "int"], ["n_top_uniform", "int"], ["n_top_stretch", "int"],
    ["n_front_stretch", "int"], ["n_front_uniform", "int"], ["n_back_uniform", "int"], ["n_back_stretch", "int"],
    ["r_left", "float"], ["r_right", "float"], ["r_bottom", "float"], ["r_top", "float"], ["r_front", "float"], ["r_back", "float"],
    ["relax", "float"], ["flag_plot", "bool"], ["flag_preplot", "bool"],
  ];
  const TWOLAYER_2D_INPUT_FIELDS = [
    ["scale_ref", "float"], ["Lx", "float"], ["Ly", "float"],
    ["x_center_dense", "float"], ["y_center_dense", "float"], ["Lx_dense", "float"], ["Ly_dense", "float"],
    ["Nx_dense", "int"], ["Ny_dense", "int"],
    ["len_left", "float"], ["len_right", "float"], ["len_bottom", "float"], ["len_top", "float"],
    ["n_left_stretch", "int"], ["n_left_uniform", "int"], ["n_right_uniform", "int"], ["n_right_stretch", "int"],
    ["n_bottom_stretch", "int"], ["n_bottom_uniform", "int"], ["n_top_uniform", "int"], ["n_top_stretch", "int"],
    ["r_left", "float"], ["r_right", "float"], ["r_bottom", "float"], ["r_top", "float"],
    ["relax", "float"], ["flag_plot", "bool"], ["flag_preplot", "bool"],
  ];

  const el = {
    caseDir: document.getElementById("caseDir"),
    loadCase: document.getElementById("loadCase"),
    fitView: document.getElementById("fitView"),
    topView: document.getElementById("topView"),
    isoView: document.getElementById("isoView"),
    xyView: document.getElementById("xyView"),
    xzView: document.getElementById("xzView"),
    yzView: document.getElementById("yzView"),
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
    loadedFiles: document.getElementById("loadedFiles"),
    geometryFile: document.getElementById("geometryFile"),
    importGeometry: document.getElementById("importGeometry"),
    appendGeometry: document.getElementById("appendGeometry"),
    exportStl: document.getElementById("exportStl"),
    bodyList: document.getElementById("bodyList"),
    moveX: document.getElementById("moveX"),
    moveY: document.getElementById("moveY"),
    moveZ: document.getElementById("moveZ"),
    rotX: document.getElementById("rotX"),
    rotY: document.getElementById("rotY"),
    rotZ: document.getElementById("rotZ"),
    bodyScale: document.getElementById("bodyScale"),
    applyBodyTransform: document.getElementById("applyBodyTransform"),
    removeBodies: document.getElementById("removeBodies"),
    meshAxes: document.getElementById("meshAxes"),
    meshInputFile: document.getElementById("meshInputFile"),
    loadMeshInput: document.getElementById("loadMeshInput"),
    scaleRef: document.getElementById("scaleRef"),
    relax: document.getElementById("relax"),
    previewMesh: document.getElementById("previewMesh"),
    saveMeshInput: document.getElementById("saveMeshInput"),
    generateMesh: document.getElementById("generateMesh"),
  };

  const state = {
    surface: null,
    mesh: { x: null, y: null, z: null, denseBox: null },
    loadedFiles: [],
    meshControlsReady: false,
    meshPreviewSuspended: false,
    bounds: null,
    angleX: 0.62,
    angleY: -0.78,
    viewMode: "iso",
    zoom: 1,
    panX: 0,
    panY: 0,
    dragging: false,
    interactingUntil: 0,
    lastX: 0,
    lastY: 0,
    framePending: false,
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
    el.xyView.addEventListener("click", () => planeView("xy"));
    el.xzView.addEventListener("click", () => planeView("xz"));
    el.yzView.addEventListener("click", () => planeView("yz"));
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
    window.addEventListener("mouseup", () => {
      if (state.dragging) {
        state.dragging = false;
        requestDraw();
      }
    });
    el.viewport.addEventListener("wheel", zoom, { passive: false });
    el.importGeometry.addEventListener("click", () => importGeometry(false));
    el.appendGeometry.addEventListener("click", () => importGeometry(true));
    el.exportStl.addEventListener("click", exportStl);
    el.applyBodyTransform.addEventListener("click", applyBodyTransform);
    el.removeBodies.addEventListener("click", removeSelectedBodies);
    el.loadMeshInput.addEventListener("click", loadSelectedMeshInput);
    el.previewMesh.addEventListener("click", previewMeshFromControls);
    el.saveMeshInput.addEventListener("click", saveMeshInput);
    el.generateMesh.addEventListener("click", generateMesh);
    el.scaleRef.addEventListener("input", previewMeshFromControls);
    el.relax.addEventListener("input", previewMeshFromControls);
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
      state.loadedFiles = [];

      if (report.surface) {
        addLoadedFile("surface", "unstruc_surface_in.dat", "case surface");
        loads.push(fetchText(`/api/surface${loadedQuery}`).then((text) => {
          state.surface = parseSurface(text);
        }));
      }
      if (report.mesh) {
        state.mesh.denseBox = report.mesh.dense_box || null;
        ["x", "y", "z"].forEach((axis) => {
          loads.push(fetchText(`/api/grid${loadedQuery}&axis=${axis}`)
            .then((text) => {
              state.mesh[axis] = parseGridAxis(text);
              addLoadedFile(axis, `${axis}grid.dat`, "case grid");
            })
            .catch(() => { state.mesh[axis] = null; }));
        });
      }

      await Promise.all(loads);
      await loadMeshInputControls({ preview: !report.mesh });
      recomputeBounds();
      fit();
      if (report.mesh || !state.mesh.x || !state.mesh.y) {
        setStatus(formatReport(report));
      } else {
        updateStats();
      }
    } catch (err) {
      setStatus(String(err));
    }
    renderLoadedFiles();
    renderBodyList();
    updateCommands();
  }

  async function readFiles(files) {
    let loadedMeshInput = false;
    for (const file of Array.from(files)) {
      const text = await file.text();
      const lower = file.name.toLowerCase();
      if (lower.includes("unstruc_surface")) {
        state.surface = parseSurface(text);
        addLoadedFile("surface", file.name, "dropped surface");
      } else if (lower.endsWith(".stl")) {
        setStatus("STL selected. Use Geometry > Import or Append STL.");
        addLoadedFile(`stl:${file.name}`, file.name, "selected STL");
      } else if (isMeshInputName(lower)) {
        const params = parseMeshInputText(text);
        fillMeshControls(params);
        state.meshControlsReady = true;
        previewMeshFromControls();
        loadedMeshInput = true;
        addLoadedFile("mesh-input", file.name, "loaded input");
      } else if (lower.startsWith("xgrid")) {
        state.mesh.x = parseGridAxis(text);
        addLoadedFile("x", file.name, "dropped grid");
      } else if (lower.startsWith("ygrid")) {
        state.mesh.y = parseGridAxis(text);
        addLoadedFile("y", file.name, "dropped grid");
      } else if (lower.startsWith("zgrid")) {
        state.mesh.z = parseGridAxis(text);
        addLoadedFile("z", file.name, "dropped grid");
      }
    }
    if (!loadedMeshInput && state.mesh.x && state.mesh.y) {
      state.mesh.denseBox = inferDenseBox();
      fillMeshControls(paramsFromCurrentGrid());
      state.meshControlsReady = true;
    }
    recomputeBounds();
    fit();
    updateStats();
    renderLoadedFiles();
    renderBodyList();
  }

  async function loadSelectedMeshInput() {
    const file = el.meshInputFile.files && el.meshInputFile.files[0];
    if (!file) {
      setStatus("Choose a mesh_input_twolayers.dat file first.");
      return;
    }
    const params = parseMeshInputText(await file.text());
    fillMeshControls(params);
    state.meshControlsReady = true;
    previewMeshFromControls();
    addLoadedFile("mesh-input", file.name, "loaded input");
    renderLoadedFiles();
    setStatus(`Loaded mesh input: ${file.name}`);
  }

  function addLoadedFile(id, name, kind) {
    state.loadedFiles = state.loadedFiles.filter((item) => item.id !== id);
    state.loadedFiles.push({ id, name, kind });
  }

  function renderLoadedFiles() {
    if (!el.loadedFiles) return;
    if (!state.loadedFiles.length) {
      el.loadedFiles.innerHTML = `<div class="item-row"><span class="item-meta">No files loaded</span></div>`;
      return;
    }
    el.loadedFiles.innerHTML = state.loadedFiles.map((item) => `
      <div class="item-row">
        <div class="item-main" title="${escapeHtml(item.name)}">${escapeHtml(item.name)}<br><span class="item-meta">${escapeHtml(item.kind)}</span></div>
        <button type="button" data-remove-file="${escapeHtml(item.id)}">Remove</button>
      </div>
    `).join("");
    el.loadedFiles.querySelectorAll("[data-remove-file]").forEach((button) => {
      button.addEventListener("click", () => removeLoadedFile(button.dataset.removeFile));
    });
  }

  function removeLoadedFile(id) {
    if (id === "surface") state.surface = null;
    if (id === "x") state.mesh.x = null;
    if (id === "y") state.mesh.y = null;
    if (id === "z") state.mesh.z = null;
    if (id === "mesh-input") {
      fillMeshControls(defaultMeshParams());
      state.meshControlsReady = true;
    }
    state.loadedFiles = state.loadedFiles.filter((item) => item.id !== id);
    if (!state.mesh.x || !state.mesh.y) state.mesh.denseBox = null;
    recomputeBounds();
    updateStats();
    renderLoadedFiles();
    renderBodyList();
    requestDraw();
  }

  function renderBodyList() {
    if (!el.bodyList) return;
    if (!state.surface || !state.surface.bodies.length) {
      el.bodyList.innerHTML = `<div class="item-row"><span class="item-meta">No surface bodies</span></div>`;
      return;
    }
    el.bodyList.innerHTML = state.surface.bodies.map((body, index) => {
      const bounds = bodyBounds(body);
      const label = `Body ${index + 1}`;
      const meta = `${body.nodeCount} nodes, ${body.elemCount} elems | x ${formatShort(bounds.min[0])}..${formatShort(bounds.max[0])}`;
      return `
        <div class="item-row">
          <label>
            <input type="checkbox" data-body-id="${index + 1}">
            <span class="item-main">${label}<br><span class="item-meta">${meta}</span></span>
          </label>
        </div>
      `;
    }).join("");
  }

  function selectedBodyIds() {
    return Array.from(el.bodyList.querySelectorAll("[data-body-id]:checked")).map((node) => Number(node.dataset.bodyId));
  }

  function bodyBounds(body) {
    const min = [Infinity, Infinity, Infinity];
    const max = [-Infinity, -Infinity, -Infinity];
    for (let i = 0; i < body.nodeCount; i += 1) {
      for (let axis = 0; axis < 3; axis += 1) {
        const value = body.points[i * 3 + axis];
        min[axis] = Math.min(min[axis], value);
        max[axis] = Math.max(max[axis], value);
      }
    }
    return { min, max };
  }

  async function applyBodyTransform() {
    const ids = selectedBodyIds();
    if (!ids.length) {
      setStatus("Select at least one body first.");
      return;
    }
    const payload = {
      case_dir: el.caseDir.value.trim(),
      body_ids: ids,
      translate: [numValue(el.moveX), numValue(el.moveY), numValue(el.moveZ)],
      rotation: [numValue(el.rotX), numValue(el.rotY), numValue(el.rotZ)],
      scale: numValue(el.bodyScale, 1),
    };
    try {
      await requireGeometryTransformApi();
      await postJson("/api/geometry/transform", payload);
      await loadCase();
      setStatus(`Transformed body ${ids.join(", ")}.`);
    } catch (err) {
      setStatus(`Body transform failed: ${err.message || err}`);
    }
  }

  async function removeSelectedBodies() {
    const ids = selectedBodyIds();
    if (!ids.length) {
      setStatus("Select at least one body first.");
      return;
    }
    try {
      await requireGeometryTransformApi();
      await postJson("/api/geometry/remove-bodies", { case_dir: el.caseDir.value.trim(), body_ids: ids });
      await loadCase();
      setStatus(`Removed body ${ids.join(", ")}.`);
    } catch (err) {
      setStatus(`Remove body failed: ${err.message || err}`);
    }
  }

  async function requireGeometryTransformApi() {
    const health = await fetchJson("/api/health");
    if (!health.geometry_transform) {
      throw new Error("Backend is still running an old API. Stop the console server and restart `python -B picar_console.py` before editing bodies.");
    }
  }

  function isMeshInputName(name) {
    return name === "input.dat" || name.includes("mesh_input") || name.includes("input_mesh");
  }

  function parseMeshInputText(text) {
    const values = [];
    text.split(/\r?\n/).forEach((rawLine) => {
      const line = rawLine.split("!", 1)[0].trim();
      if (!line) return;
      const token = line.split(/\s+/)[0];
      values.push(parseScalar(token));
    });
    const fields = values.length >= MESH_INPUT_FIELDS.length ? MESH_INPUT_FIELDS : TWOLAYER_2D_INPUT_FIELDS;
    if (values.length < fields.length) {
      throw new Error(`Mesh input has ${values.length} values; expected at least ${fields.length}.`);
    }
    const params = defaultMeshParams();
    fields.forEach(([key, kind], index) => {
      const value = values[index];
      if (kind === "int") params[key] = Math.trunc(Number(value));
      else if (kind === "bool") params[key] = Boolean(value);
      else params[key] = Number(value);
    });
    if (fields === TWOLAYER_2D_INPUT_FIELDS) {
      params.Lz = 0;
      params.z_center_dense = 0;
      params.Lz_dense = 0;
      params.Nz_dense = 0;
      params.len_front = 0;
      params.len_back = 0;
      params.n_front_stretch = 0;
      params.n_front_uniform = 0;
      params.n_back_uniform = 0;
      params.n_back_stretch = 0;
      params.r_front = 1;
      params.r_back = 1;
    }
    return params;
  }

  function parseScalar(token) {
    const lowered = String(token).trim().toLowerCase();
    if (["true", "t", ".true."].includes(lowered)) return true;
    if (["false", "f", ".false."].includes(lowered)) return false;
    const value = Number(lowered.replace(/[dD]/, "e"));
    if (!Number.isFinite(value)) throw new Error(`Invalid mesh input value: ${token}`);
    return value;
  }

  function paramsFromCurrentGrid() {
    const x = axisParamsFromValues(state.mesh.x);
    const y = axisParamsFromValues(state.mesh.y);
    const z = state.mesh.z && state.mesh.z.length > 1 ? axisParamsFromValues(state.mesh.z) : null;
    const p = defaultMeshParams();
    return {
      ...p,
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
      n_left_uniform: 0,
      n_right_uniform: 0,
      n_right_stretch: x.rightStretch,
      n_bottom_stretch: y.leftStretch,
      n_bottom_uniform: 0,
      n_top_uniform: 0,
      n_top_stretch: y.rightStretch,
      n_front_stretch: z ? z.leftStretch : 0,
      n_front_uniform: 0,
      n_back_uniform: 0,
      n_back_stretch: z ? z.rightStretch : 0,
      len_left: 0,
      len_right: 0,
      len_bottom: 0,
      len_top: 0,
      len_front: 0,
      len_back: 0,
    };
  }

  function axisParamsFromValues(values) {
    const start = values[0];
    const end = values[values.length - 1];
    const length = end - start;
    const range = inferDenseRange(values) || [start, end];
    const spacing = [];
    for (let i = 0; i < values.length - 1; i += 1) spacing.push(values[i + 1] - values[i]);
    let denseCount = 0;
    let leftStretch = 0;
    let rightStretch = 0;
    for (let i = 0; i < spacing.length; i += 1) {
      const a = values[i];
      const b = values[i + 1];
      if (a >= range[0] - 1e-10 && b <= range[1] + 1e-10) denseCount += 1;
      else if (b <= range[0] + 1e-10) leftStretch += 1;
      else if (a >= range[1] - 1e-10) rightStretch += 1;
    }
    return {
      length,
      center: 0.5 * (range[0] + range[1]) - start,
      denseLength: Math.max(0, range[1] - range[0]),
      denseCount,
      leftStretch,
      rightStretch,
    };
  }

  async function loadMeshInputControls(options = {}) {
    const preview = options.preview === true;
    try {
      const query = `?case_dir=${encodeURIComponent(el.caseDir.value.trim())}`;
      const payload = await fetchJson(`/api/mesh-input${query}`);
      fillMeshControls(payload.params);
      state.meshControlsReady = true;
      if (preview) previewMeshFromControls();
    } catch (err) {
      state.meshControlsReady = true;
      fillMeshControls(defaultMeshParams());
      if (preview) previewMeshFromControls();
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
    el.meshAxes.innerHTML = defs.map(([axis, title, lowName, highName]) => `
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
    `).join("");
    el.meshAxes.querySelectorAll("input").forEach((input) => input.addEventListener("input", previewMeshFromControls));
  }

  function fillMeshControls(params) {
    state.meshPreviewSuspended = true;
    const p = params || {};
    const start = previewStarts();
    const xStart = start.x;
    const yStart = start.y;
    const zStart = start.z;
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

  function readMeshParams() {
    const x = readAxisControls("x");
    const y = readAxisControls("y");
    const z = readAxisControls("z");
    validateAxisControls("x", x);
    validateAxisControls("y", y);
    if (z.end > z.start || z.denseCount > 0) validateAxisControls("z", z, true);
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
      state.mesh.x = makeAxisNodesFromControls("x");
      state.mesh.y = makeAxisNodesFromControls("y");
      state.mesh.z = params.Lz > 0 && axisIntervalCount("z") > 0 ? makeAxisNodesFromControls("z") : null;
      const x = readAxisControls("x");
      const y = readAxisControls("y");
      const z = readAxisControls("z");
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
    const result = await postJson("/api/mesh/save", { case_dir: el.caseDir.value.trim(), params: readMeshParams() });
    previewMeshFromControls();
    setStatus(`Mesh input saved: ${result.path || "mesh_input_twolayers.dat"}`);
  }

  function readMeshOrigin() {
    return {
      x: numId("xStart"),
      y: numId("yStart"),
      z: numId("zStart"),
    };
  }

  function axisIntervalCount(axis) {
    const cfg = readAxisControls(axis);
    return cfg.leftStretch + cfg.leftUniform + cfg.denseCount + cfg.rightUniform + cfg.rightStretch;
  }

  async function generateMesh() {
    try {
      const health = await fetchJson("/api/health");
      if (!health.origin_shift) {
        throw new Error("Backend is still running an old mesh generator API. Stop the console server and restart `python -B picar_console.py` before Generate XYZ.");
      }
      const result = await postJson("/api/mesh/generate", { case_dir: el.caseDir.value.trim(), params: readMeshParams(), origin: readMeshOrigin() });
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
    renderLoadedFiles();
    renderBodyList();
    setStatus(append ? "Geometry appended." : "Geometry imported.");
  }

  async function exportStl() {
    const result = await postJson("/api/geometry/export-stl", { case_dir: el.caseDir.value.trim(), output: "surface_export.stl" });
    setStatus(`STL exported: ${result.path}`);
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
      const nodeMap = new Map();
      for (let n = 0; n < nodeCount; n += 1) {
        const nodeId = Math.trunc(values[i++]);
        nodeMap.set(nodeId, n);
        points[n * 3] = values[i++];
        points[n * 3 + 1] = values[i++];
        points[n * 3 + 2] = values[i++];
      }
      const elems = new Int32Array(elemCount * 3);
      for (let e = 0; e < elemCount; e += 1) {
        i += 1;
        elems[e * 3] = nodeMap.get(Math.trunc(values[i++])) ?? -1;
        elems[e * 3 + 1] = nodeMap.get(Math.trunc(values[i++])) ?? -1;
        elems[e * 3 + 2] = nodeMap.get(Math.trunc(values[i++])) ?? -1;
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

  function previewStarts() {
    const surface = surfaceBounds();
    return {
      x: state.mesh.x && state.mesh.x.length ? state.mesh.x[0] : (surface ? surface.min[0] : 0),
      y: state.mesh.y && state.mesh.y.length ? state.mesh.y[0] : (surface ? surface.min[1] : 0),
      z: state.mesh.z && state.mesh.z.length ? state.mesh.z[0] : (surface ? surface.min[2] : 0),
    };
  }

  function surfaceBounds() {
    if (!state.surface || !state.surface.bodies.length) return null;
    const min = [Infinity, Infinity, Infinity];
    const max = [-Infinity, -Infinity, -Infinity];
    state.surface.bodies.forEach((body) => {
      for (let i = 0; i < body.nodeCount; i += 1) {
        const x = body.points[i * 3];
        const y = body.points[i * 3 + 1];
        const z = body.points[i * 3 + 2];
        min[0] = Math.min(min[0], x);
        min[1] = Math.min(min[1], y);
        min[2] = Math.min(min[2], z);
        max[0] = Math.max(max[0], x);
        max[1] = Math.max(max[1], y);
        max[2] = Math.max(max[2], z);
      }
    });
    return Number.isFinite(min[0]) ? { min, max } : null;
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
      const isInteractive = state.dragging || performance.now() < state.interactingUntil;
      const triangleBudget = isInteractive ? INTERACTIVE_SURFACE_TRIANGLES : MAX_SURFACE_TRIANGLES;
      const triStride = body.elemCount <= triangleBudget ? 1 : Math.ceil(body.elemCount / triangleBudget);
      if (el.showSurfaceLines.checked && body.elemCount) {
        drawSurfaceTriangleWire(ctx, rect, body, triStride);
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
    if (isPlaneView()) {
      drawPlaneAxesAndTicks(ctx, rect);
      return;
    }
    const b = state.bounds;
    const box = { x0: b.min[0], x1: b.max[0], y0: b.min[1], y1: b.max[1], z0: b.min[2], z1: b.max[2] };
    drawBoxEdges(ctx, rect, box, "rgba(120, 130, 140, 0.26)", 0.8);
    drawFloorGrid(ctx, rect, box);
    drawAxis(ctx, rect, [box.x0, box.y0, box.z0], [box.x1, box.y0, box.z0], "X Axis", ticks(box.x0, box.x1), 0);
    drawAxis(ctx, rect, [box.x0, box.y0, box.z0], [box.x0, box.y1, box.z0], "Y Axis", ticks(box.y0, box.y1), 1);
    drawAxis(ctx, rect, [box.x0, box.y0, box.z0], [box.x0, box.y0, box.z1], "Z Axis", ticks(box.z0, box.z1), 2);
  }

  function drawPlaneAxesAndTicks(ctx, rect) {
    const b = state.bounds;
    const axes = planeAxes(state.viewMode);
    const uTicks = ticks(b.min[axes.u], b.max[axes.u]);
    const vTicks = ticks(b.min[axes.v], b.max[axes.v]);
    const d0 = b.min[axes.d];
    const corner = (u, v) => planePoint(axes, u, v, d0);
    const u0 = b.min[axes.u];
    const u1 = b.max[axes.u];
    const v0 = b.min[axes.v];
    const v1 = b.max[axes.v];

    ctx.strokeStyle = "rgba(160, 166, 172, 0.22)";
    ctx.lineWidth = 0.7;
    uTicks.forEach((u) => linePoints(ctx, rect, corner(u, v0), corner(u, v1)));
    vTicks.forEach((v) => linePoints(ctx, rect, corner(u0, v), corner(u1, v)));

    ctx.strokeStyle = "rgba(120, 130, 140, 0.42)";
    ctx.lineWidth = 1;
    linePoints(ctx, rect, corner(u0, v0), corner(u1, v0));
    linePoints(ctx, rect, corner(u1, v0), corner(u1, v1));
    linePoints(ctx, rect, corner(u1, v1), corner(u0, v1));
    linePoints(ctx, rect, corner(u0, v1), corner(u0, v0));

    drawPlaneAxis(ctx, rect, axes, u0, v0, u1, v0, `${axisName(axes.u)} Axis`, uTicks, axes.u);
    drawPlaneAxis(ctx, rect, axes, u0, v0, u0, v1, `${axisName(axes.v)} Axis`, vTicks, axes.v);
  }

  function drawPlaneAxis(ctx, rect, axes, uStart, vStart, uEnd, vEnd, label, tickValues, tickAxis) {
    const d0 = state.bounds.min[axes.d];
    ctx.strokeStyle = "#22282e";
    ctx.fillStyle = "#22282e";
    ctx.lineWidth = 1.6;
    linePoints(ctx, rect, planePoint(axes, uStart, vStart, d0), planePoint(axes, uEnd, vEnd, d0));
    const end = projectPoint(rect, ...planePoint(axes, uEnd, vEnd, d0));
    ctx.font = "15px Segoe UI, Arial";
    ctx.fillText(label, end.x + 8, end.y - 8);
    ctx.font = "12px Segoe UI, Arial";
    tickValues.forEach((value) => {
      const u = tickAxis === axes.u ? value : uStart;
      const v = tickAxis === axes.v ? value : vStart;
      const p = projectPoint(rect, ...planePoint(axes, u, v, d0));
      ctx.fillRect(p.x - 2, p.y - 2, 4, 4);
      ctx.fillText(formatTick(value), p.x + 5, p.y + 14);
    });
  }

  function planePoint(axes, u, v, d) {
    const point = [0, 0, 0];
    point[axes.u] = u;
    point[axes.v] = v;
    point[axes.d] = d;
    return point;
  }

  function axisName(index) {
    return ["X", "Y", "Z"][index] || "";
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

  function drawSurfaceTriangleWire(ctx, rect, body, triStride) {
    ctx.beginPath();
    for (let e = 0; e < body.elemCount; e += triStride) {
      const triangle = projectedTriangle(rect, body, e);
      if (!triangle) continue;
      const { pa, pb, pc } = triangle;
      ctx.moveTo(pa.x, pa.y);
      ctx.lineTo(pb.x, pb.y);
      ctx.lineTo(pc.x, pc.y);
      ctx.closePath();
    }
    ctx.strokeStyle = "rgba(20, 54, 82, 0.24)";
    ctx.lineWidth = (state.dragging || performance.now() < state.interactingUntil) ? 0.28 : 0.32;
    ctx.stroke();
  }

  function projectedTriangle(rect, body, elemIndex) {
    const a = body.elems[elemIndex * 3];
    const b = body.elems[elemIndex * 3 + 1];
    const c = body.elems[elemIndex * 3 + 2];
    if (!validBodyPointIndex(body, a) || !validBodyPointIndex(body, b) || !validBodyPointIndex(body, c)) return null;
    const pa = projectBodyPoint(rect, body, a);
    const pb = projectBodyPoint(rect, body, b);
    const pc = projectBodyPoint(rect, body, c);
    return { pa, pb, pc, depth: (pa.depth + pb.depth + pc.depth) / 3 };
  }

  function validBodyPointIndex(body, index) {
    return Number.isInteger(index) && index >= 0 && index < body.nodeCount;
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
    if (isPlaneView()) return projectPlanePoint(rect, x, y, z, b);
    const cx = (b.min[0] + b.max[0]) / 2;
    const cy = (b.min[1] + b.max[1]) / 2;
    const cz = (b.min[2] + b.max[2]) / 2;
    const px = x - cx;
    const py = y - cy;
    const pz = z - cz;
    const basis = cameraBasis();
    const scale = 0.78 * Math.min(rect.width, rect.height) / Math.max(b.span, 1e-12) * state.zoom;
    return {
      x: rect.width / 2 + state.panX + dot3([px, py, pz], basis.right) * scale,
      y: rect.height / 2 + state.panY - dot3([px, py, pz], basis.up) * scale,
      depth: dot3([px, py, pz], basis.forward),
    };
  }

  function cameraBasis() {
    const elevation = state.angleX;
    const azimuth = state.angleY;
    const cosElev = Math.cos(elevation);
    if (Math.abs(cosElev) < 0.03) {
      const topSign = elevation >= 0 ? 1 : -1;
      return {
        right: [1, 0, 0],
        up: [0, topSign, 0],
        forward: [0, 0, -topSign],
      };
    }
    const camera = normalize3([
      cosElev * Math.cos(azimuth),
      cosElev * Math.sin(azimuth),
      Math.sin(elevation),
    ]);
    const forward = [-camera[0], -camera[1], -camera[2]];
    const right = normalize3(cross3(forward, [0, 0, 1]));
    const up = normalize3(cross3(right, forward));
    return { right, up, forward };
  }

  function dot3(a, b) {
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  }

  function cross3(a, b) {
    return [
      a[1] * b[2] - a[2] * b[1],
      a[2] * b[0] - a[0] * b[2],
      a[0] * b[1] - a[1] * b[0],
    ];
  }

  function normalize3(v) {
    const length = Math.hypot(v[0], v[1], v[2]) || 1;
    return [v[0] / length, v[1] / length, v[2] / length];
  }

  function projectPlanePoint(rect, x, y, z, bounds) {
    const axes = planeAxes(state.viewMode);
    const values = [x, y, z];
    const u = values[axes.u];
    const v = values[axes.v];
    const d = values[axes.d];
    const u0 = bounds.min[axes.u];
    const u1 = bounds.max[axes.u];
    const v0 = bounds.min[axes.v];
    const v1 = bounds.max[axes.v];
    const du = Math.max(u1 - u0, 1e-12);
    const dv = Math.max(v1 - v0, 1e-12);
    const scale = 0.84 * Math.min(rect.width / du, rect.height / dv) * state.zoom;
    return {
      x: rect.width / 2 + state.panX + (u - 0.5 * (u0 + u1)) * scale,
      y: rect.height / 2 + state.panY - (v - 0.5 * (v0 + v1)) * scale,
      depth: d,
    };
  }

  function planeAxes(mode) {
    if (mode === "xy") return { u: 0, v: 1, d: 2 };
    if (mode === "xz") return { u: 0, v: 2, d: 1 };
    if (mode === "yz") return { u: 1, v: 2, d: 0 };
    return { u: 0, v: 1, d: 2 };
  }

  function isPlaneView() {
    return state.viewMode === "xy" || state.viewMode === "xz" || state.viewMode === "yz";
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
    if (maxSpacing / minSpacing <= DENSE_UNIFORM_RATIO) return [values[0], values[values.length - 1]];
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

  function formatShort(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return "0";
    return Number(number.toPrecision(5)).toString();
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (ch) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }[ch]));
  }

  function fit() {
    state.zoom = 1;
    state.panX = 0;
    state.panY = 0;
    requestDraw();
  }

  function topView() {
    state.viewMode = "top";
    state.angleX = 1.55;
    state.angleY = 0;
    setActiveViewButton(el.topView);
    requestDraw();
  }

  function isoView() {
    state.viewMode = "iso";
    state.angleX = 0.62;
    state.angleY = -0.78;
    setActiveViewButton(el.isoView);
    requestDraw();
  }

  function planeView(mode) {
    state.viewMode = mode;
    setActiveViewButton({ xy: el.xyView, xz: el.xzView, yz: el.yzView }[mode]);
    fit();
  }

  function setActiveViewButton(activeButton) {
    [el.topView, el.isoView, el.xyView, el.xzView, el.yzView].forEach((button) => {
      if (button) button.classList.toggle("active", button === activeButton);
    });
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
    if (isPlaneView()) {
      state.panX += dx;
      state.panY += dy;
    } else {
      state.angleY += dx * 0.008;
      state.angleX += dy * 0.008;
      state.angleX = Math.max(-1.55, Math.min(1.55, state.angleX));
    }
    state.lastX = event.clientX;
    state.lastY = event.clientY;
    requestDraw();
  }

  function zoom(event) {
    event.preventDefault();
    state.zoom *= event.deltaY < 0 ? 1.12 : 0.89;
    state.zoom = Math.max(0.05, Math.min(80, state.zoom));
    state.interactingUntil = performance.now() + 180;
    requestDraw();
    window.clearTimeout(state.zoomSettleTimer);
    state.zoomSettleTimer = window.setTimeout(requestDraw, 200);
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
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const text = await res.text();
    const data = text ? JSON.parse(text) : {};
    if (!res.ok || data.ok === false) throw new Error(data.error || text || res.statusText);
    return data;
  }
}());
