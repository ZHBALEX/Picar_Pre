(function () {
  const MAX_SURFACE_POINTS = 35000;
  const MAX_SURFACE_TRIANGLES = 80000;
  const INTERACTIVE_SURFACE_TRIANGLES = 12000;
  const MAX_GRID_LINES = 28;
  const MAX_DRAWN_PROBES = 6000;
  const DENSE_UNIFORM_RATIO = 1.05;
  const AMR_COLORS = ["#d62828", "#2f80ed", "#f59f00", "#7b2cbf", "#2b9348", "#d9480f"];
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
    resetView: document.getElementById("resetView"),
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
    exportPlotJson: document.getElementById("exportPlotJson"),
    exportPlotPng: document.getElementById("exportPlotPng"),
    showSurfacePoints: document.getElementById("showSurfacePoints"),
    showSurfaceLines: document.getElementById("showSurfaceLines"),
    showMeshBounds: document.getElementById("showMeshBounds"),
    showDenseRegion: document.getElementById("showDenseRegion"),
    showAmrRegions: document.getElementById("showAmrRegions"),
    probeLayerControl: document.getElementById("probeLayerControl"),
    showProbes: document.getElementById("showProbes"),
    showFullMesh: document.getElementById("showFullMesh"),
    showFortMotion: document.getElementById("showFortMotion"),
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
    amrResize: document.getElementById("amrResize"),
    amrList: document.getElementById("amrList"),
    saveAmr: document.getElementById("saveAmr"),
    probeGenerateBody: document.getElementById("probeGenerateBody"),
    probePlaneAxis: document.getElementById("probePlaneAxis"),
    probePlaneValue: document.getElementById("probePlaneValue"),
    probeSamples: document.getElementById("probeSamples"),
    probeTolerance: document.getElementById("probeTolerance"),
    probeBandFactor: document.getElementById("probeBandFactor"),
    probeSides: document.getElementById("probeSides"),
    probeDeduplicate: document.getElementById("probeDeduplicate"),
    generateProbes: document.getElementById("generateProbes"),
    probeEditType: document.getElementById("probeEditType"),
    probeEditIndex: document.getElementById("probeEditIndex"),
    probeMarkerFields: document.getElementById("probeMarkerFields"),
    probeEditBody: document.getElementById("probeEditBody"),
    probeEditReference: document.getElementById("probeEditReference"),
    probeEditX: document.getElementById("probeEditX"),
    probeEditY: document.getElementById("probeEditY"),
    probeEditZ: document.getElementById("probeEditZ"),
    moveProbeToReference: document.getElementById("moveProbeToReference"),
    applyProbeEdit: document.getElementById("applyProbeEdit"),
    addMarkerProbe: document.getElementById("addMarkerProbe"),
    addFluidProbe: document.getElementById("addFluidProbe"),
    deleteProbe: document.getElementById("deleteProbe"),
    saveProbes: document.getElementById("saveProbes"),
    reloadProbes: document.getElementById("reloadProbes"),
    probeReport: document.getElementById("probeReport"),
    syncProfile: document.getElementById("syncProfile"),
    syncFortStart: document.getElementById("syncFortStart"),
    previewSetupSync: document.getElementById("previewSetupSync"),
    applySetupSync: document.getElementById("applySetupSync"),
    setupSyncReport: document.getElementById("setupSyncReport"),
    fortList: document.getElementById("fortList"),
    fortBody: document.getElementById("fortBody"),
    fortFrame: document.getElementById("fortFrame"),
    fortSamples: document.getElementById("fortSamples"),
    fortOrder: document.getElementById("fortOrder"),
    fortMode: document.getElementById("fortMode"),
    previewFort: document.getElementById("previewFort"),
    clearFort: document.getElementById("clearFort"),
  };

  const state = {
    surface: null,
    mesh: { x: null, y: null, z: null, denseBox: null },
    amr: null,
    probes: null,
    probeEditing: false,
    probeTarget: null,
    probeResolveRequest: 0,
    fort: null,
    motion: null,
    loadedFiles: [],
    meshControlsReady: false,
    meshPreviewSuspended: false,
    pendingGeometryFile: null,
    bounds: null,
    angleX: 0.62,
    angleY: -0.78,
    viewMode: "iso",
    zoom: 1,
    panX: 0,
    panY: 0,
    dragging: false,
    dragMode: null,
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
    el.resetView.addEventListener("click", resetView);
    el.topView.addEventListener("click", topView);
    el.isoView.addEventListener("click", isoView);
    el.xyView.addEventListener("click", () => planeView("xy"));
    el.xzView.addEventListener("click", () => planeView("xz"));
    el.yzView.addEventListener("click", () => planeView("yz"));
    el.exportPlotJson.addEventListener("click", exportPlotJson);
    el.exportPlotPng.addEventListener("click", exportPlotPng);
    el.fileInput.addEventListener("change", () => readFiles(el.fileInput.files));
    ["dragenter", "dragover"].forEach((name) => el.dropzone.addEventListener(name, onDrag));
    ["dragleave", "drop"].forEach((name) => el.dropzone.addEventListener(name, offDrag));
    el.dropzone.addEventListener("drop", (event) => readFiles(event.dataTransfer.files));
    [
      el.showSurfacePoints,
      el.showSurfaceLines,
      el.showMeshBounds,
      el.showDenseRegion,
      el.showAmrRegions,
      el.showProbes,
      el.showFullMesh,
      el.showFortMotion,
      el.showAxes,
    ].forEach((node) => node.addEventListener("change", requestDraw));
    el.viewport.addEventListener("mousedown", startDrag);
    window.addEventListener("mousemove", drag);
    window.addEventListener("mouseup", () => {
      if (state.dragging) {
        state.dragging = false;
        state.dragMode = null;
        el.viewport.classList.remove("panning");
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
    el.amrResize.addEventListener("change", updateAmrFromControls);
    el.saveAmr.addEventListener("click", saveAmr);
    el.generateProbes.addEventListener("click", generateProbePreview);
    el.probeEditType.addEventListener("change", () => {
      stopProbeEditing();
      renderProbePanel();
    });
    el.probeEditIndex.addEventListener("pointerdown", beginProbeEditing);
    el.probeEditIndex.addEventListener("change", () => {
      fillSelectedProbeFields();
      beginProbeEditing();
    });
    el.probeEditBody.addEventListener("change", previewSelectedMarkerReference);
    el.probeEditReference.addEventListener("change", previewSelectedMarkerReference);
    el.moveProbeToReference.addEventListener("click", moveSelectedProbeToReference);
    el.applyProbeEdit.addEventListener("click", applySelectedProbePosition);
    el.addMarkerProbe.addEventListener("click", addMarkerProbe);
    el.addFluidProbe.addEventListener("click", addFluidProbe);
    el.deleteProbe.addEventListener("click", deleteSelectedProbe);
    el.saveProbes.addEventListener("click", saveProbes);
    el.reloadProbes.addEventListener("click", loadCase);
    el.previewSetupSync.addEventListener("click", previewSetupSync);
    el.applySetupSync.addEventListener("click", applySetupSync);
    el.previewFort.addEventListener("click", previewFortMotion);
    el.clearFort.addEventListener("click", clearFortMotion);
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
      state.amr = null;
      state.probes = null;
      stopProbeEditing();
      state.fort = report.fort || null;
      state.motion = null;
      state.loadedFiles = [];
      state.pendingGeometryFile = null;
      setProbeLayerAvailable(false);

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
      if (report.amr && report.amr.ok) {
        state.amr = normalizeAmr(report.amr);
        addLoadedFile("amr", "amr_in.dat", "case AMR");
      }
      if (report.probes && report.probes.exists) {
        setProbeLayerAvailable(true);
        loads.push(fetchJson(`/api/probes${loadedQuery}`)
          .then((probes) => {
            state.probes = normalizeProbes(probes);
            el.showProbes.checked = true;
            addLoadedFile("probes", "probe_in.dat", "case probes");
          })
          .catch((err) => {
            state.probes = normalizeProbes({
              ok: false,
              exists: true,
              path: report.probes.path || "",
              marker_count: report.probes.marker_count || 0,
              fluid_count: report.probes.fluid_count || 0,
              markers: [],
              fluids: [],
              errors: [cleanErrorMessage(err)],
            });
            addLoadedFile("probes", "probe_in.dat", "probe parse error");
          }));
      }
      if (backendSupportsFort(report)) {
        loads.push(fetchJson(`/api/fort/report${loadedQuery}`)
          .then((fort) => {
            state.fort = fort;
          })
          .catch((err) => {
            state.fort = {
              ok: false,
              body_count: report.surface ? report.surface.bodies.length : 0,
              files: [],
              error: cleanErrorMessage(err),
            };
          }));
      } else {
        state.fort = {
          ok: false,
          body_count: report.surface ? report.surface.bodies.length : 0,
          files: [],
          error: "Fort preview API is missing. Restart the console with `python -B picar_console.py`.",
        };
      }

      await Promise.all(loads);
      await loadMeshInputControls({ preview: false });
      recomputeBounds();
      fit();
      if (report.mesh || !state.mesh.x || !state.mesh.y) {
        setStatus(formatReport(report));
      } else {
        updateStats();
      }
    } catch (err) {
      setStatus(cleanErrorMessage(err));
    }
    renderLoadedFiles();
    renderBodyList();
    renderAmrPanel();
    renderFortPanel();
    renderProbePanel();
    updateCommands();
  }

  async function readFiles(files) {
    let loadedMeshInput = false;
    let importedStlCount = 0;
    for (const file of Array.from(files)) {
      try {
        const lower = file.name.toLowerCase();
        if (lower.includes("unstruc_surface")) {
          const text = await file.text();
          state.surface = parseSurface(text);
          addLoadedFile("surface", file.name, "dropped surface");
          state.pendingGeometryFile = file;
        } else if (lower.endsWith(".stl")) {
          state.pendingGeometryFile = file;
          addLoadedFile(`stl:${file.name}`, file.name, "importing STL");
          renderLoadedFiles();
          if (await importGeometry(importedStlCount > 0, file)) {
            importedStlCount += 1;
          }
        } else if (isMeshInputName(lower)) {
          const text = await file.text();
          const params = parseMeshInputText(text);
          fillMeshControls(params);
          state.meshControlsReady = true;
          previewMeshFromControls();
          loadedMeshInput = true;
          addLoadedFile("mesh-input", file.name, "loaded input");
        } else if (lower.startsWith("xgrid")) {
          const text = await file.text();
          state.mesh.x = parseGridAxis(text);
          addLoadedFile("x", file.name, "dropped grid");
        } else if (lower.startsWith("ygrid")) {
          const text = await file.text();
          state.mesh.y = parseGridAxis(text);
          addLoadedFile("y", file.name, "dropped grid");
        } else if (lower.startsWith("zgrid")) {
          const text = await file.text();
          state.mesh.z = parseGridAxis(text);
          addLoadedFile("z", file.name, "dropped grid");
        } else if (lower === "amr_in.dat" || lower.includes("amr")) {
          const text = await file.text();
          state.amr = parseAmrText(text);
          addLoadedFile("amr", file.name, "dropped AMR");
        }
      } catch (err) {
        setStatus(`Could not load ${file.name}: ${err.message || err}`);
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
    renderAmrPanel();
    renderProbePanel();
  }

  async function loadSelectedMeshInput() {
    const file = el.meshInputFile.files && el.meshInputFile.files[0];
    if (!file) {
      setStatus("Choose a mesh_input_twolayers.dat file first.");
      return;
    }
    try {
      const params = parseMeshInputText(await file.text());
      fillMeshControls(params);
      state.meshControlsReady = true;
      previewMeshFromControls();
      addLoadedFile("mesh-input", file.name, "loaded input");
      renderLoadedFiles();
      setStatus(`Loaded mesh input: ${file.name}`);
    } catch (err) {
      setStatus(`Load mesh input failed: ${err.message || err}`);
    }
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
    if (id === "amr") state.amr = null;
    if (id === "probes") {
      state.probes = null;
      setProbeLayerAvailable(false);
    }
    if (id === "mesh-input") {
      fillMeshControls(defaultMeshParams());
      state.meshControlsReady = true;
    }
    if (id.startsWith("stl:") && state.pendingGeometryFile && id === `stl:${state.pendingGeometryFile.name}`) {
      state.pendingGeometryFile = null;
    }
    state.loadedFiles = state.loadedFiles.filter((item) => item.id !== id);
    if (!state.mesh.x || !state.mesh.y) state.mesh.denseBox = null;
    recomputeBounds();
    updateStats();
    renderLoadedFiles();
    renderBodyList();
    renderAmrPanel();
    renderProbePanel();
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

  function renderAmrPanel() {
    if (!el.amrList || !el.amrResize) return;
    const amr = state.amr;
    if (!amr || !amr.layers.length) {
      el.amrResize.value = "0";
      el.amrList.innerHTML = `<div class="item-row"><span class="item-meta">No amr_in.dat loaded</span></div>`;
      return;
    }
    el.amrResize.value = String(amr.resize ?? 0);
    el.amrList.innerHTML = amr.layers.map((layer, layerIndex) => {
      const color = amrColor(layerIndex);
      const blocks = layer.blocks.map((block, blockIndex) => `
        <section class="axis-group" data-amr-block="${layerIndex}:${blockIndex}">
          <h3>Block ${escapeHtml(block.id)}</h3>
          <div class="grid three">
            <label>ID<input data-amr-field="id" type="number" step="1" value="${formatControlNumber(block.id)}"></label>
            <label>Parent<input data-amr-field="parent" type="number" step="1" value="${formatControlNumber(block.parent)}"></label>
            <label>Moving<input data-amr-field="moving" type="number" min="0" step="1" value="${formatControlNumber(block.moving)}"></label>
          </div>
          <div class="grid three">
            <label>Start X<input data-amr-field="start.0" type="number" step="0.01" value="${formatControlNumber(block.start[0])}"></label>
            <label>Start Y<input data-amr-field="start.1" type="number" step="0.01" value="${formatControlNumber(block.start[1])}"></label>
            <label>Start Z<input data-amr-field="start.2" type="number" step="0.01" value="${formatControlNumber(block.start[2])}"></label>
          </div>
          <div class="grid three">
            <label>End X<input data-amr-field="end.0" type="number" step="0.01" value="${formatControlNumber(block.end[0])}"></label>
            <label>End Y<input data-amr-field="end.1" type="number" step="0.01" value="${formatControlNumber(block.end[1])}"></label>
            <label>End Z<input data-amr-field="end.2" type="number" step="0.01" value="${formatControlNumber(block.end[2])}"></label>
          </div>
        </section>
      `).join("");
      return `
        <section class="amr-layer">
          <h3><span class="amr-swatch" style="background:${color}"></span>Layer ${escapeHtml(layer.layer)}</h3>
          ${blocks || `<div class="item-row"><span class="item-meta">No blocks</span></div>`}
        </section>
      `;
    }).join("");
    el.amrList.querySelectorAll("input").forEach((input) => {
      input.addEventListener("input", updateAmrFromControls);
    });
  }

  function updateAmrFromControls() {
    if (!state.amr) return;
    state.amr.resize = Math.trunc(numValue(el.amrResize, 0));
    el.amrList.querySelectorAll("[data-amr-block]").forEach((section) => {
      const [layerIndex, blockIndex] = String(section.dataset.amrBlock || "").split(":").map((value) => Number(value));
      const block = state.amr.layers[layerIndex] && state.amr.layers[layerIndex].blocks[blockIndex];
      if (!block) return;
      section.querySelectorAll("[data-amr-field]").forEach((input) => {
        const field = input.dataset.amrField || "";
        const value = field === "id" || field === "parent" || field === "moving"
          ? Math.trunc(numValue(input, 0))
          : numValue(input, 0);
        if (field === "id") block.id = value;
        else if (field === "parent") block.parent = value;
        else if (field === "moving") block.moving = value;
        else if (field.startsWith("start.")) block.start[Number(field.split(".")[1])] = value;
        else if (field.startsWith("end.")) block.end[Number(field.split(".")[1])] = value;
      });
    });
    recomputeBounds();
    updateStats();
    requestDraw();
  }

  async function saveAmr() {
    if (!state.amr) {
      setStatus("No AMR data to save.");
      return;
    }
    try {
      updateAmrFromControls();
      const result = await postJson("/api/amr/save", { case_dir: el.caseDir.value.trim(), amr: state.amr });
      state.amr = normalizeAmr(result.amr);
      addLoadedFile("amr", "amr_in.dat", "case AMR");
      renderLoadedFiles();
      renderAmrPanel();
      setStatus(`AMR saved: ${result.path || "amr_in.dat"}`);
    } catch (err) {
      setStatus(`Save AMR failed: ${err.message || err}`);
    }
  }

  function editableProbes() {
    if (!state.probes) {
      state.probes = normalizeProbes({ ok: true, exists: false, markers: [], fluids: [], errors: [] });
    }
    return state.probes;
  }

  function bodySelectOptions(selected) {
    const count = state.surface ? state.surface.bodies.length : 0;
    if (!count) return `<option value="1">Body 1</option>`;
    return Array.from({ length: count }, (_, index) => {
      const bodyId = index + 1;
      return `<option value="${bodyId}"${bodyId === selected ? " selected" : ""}>Body ${bodyId}</option>`;
    }).join("");
  }

  function renderProbePanel() {
    if (!el.probeEditType || !el.probeEditIndex) return;
    const generateBody = Math.max(1, Number(el.probeGenerateBody.value) || 1);
    const editBody = Math.max(1, Number(el.probeEditBody.value) || 1);
    el.probeGenerateBody.innerHTML = bodySelectOptions(generateBody);
    el.probeEditBody.innerHTML = bodySelectOptions(editBody);

    const probes = state.probes;
    const type = el.probeEditType.value === "fluid" ? "fluid" : "marker";
    const items = probes ? (type === "marker" ? probes.markers : probes.fluids) : [];
    const oldIndex = Math.max(0, Math.trunc(Number(el.probeEditIndex.value) || 0));
    el.probeEditIndex.innerHTML = items.length
      ? items.map((item, index) => {
        const label = type === "marker"
          ? `#${index + 1} | body ${item.body} | ref ${item.reference}`
          : `#${index + 1} | (${item.point.map(formatShort).join(", ")})`;
        return `<option value="${index}">${escapeHtml(label)}</option>`;
      }).join("")
      : `<option value="">No ${type} probes</option>`;
    if (items.length) el.probeEditIndex.value = String(Math.min(oldIndex, items.length - 1));
    el.probeEditIndex.disabled = !items.length;
    el.probeMarkerFields.style.display = type === "marker" ? "grid" : "none";
    el.moveProbeToReference.hidden = type !== "marker";
    el.moveProbeToReference.disabled = !items.length || !state.probeTarget;
    el.applyProbeEdit.textContent = type === "marker" ? "Snap XYZ" : "Apply XYZ";
    el.deleteProbe.disabled = !items.length;
    el.applyProbeEdit.disabled = !items.length;
    fillSelectedProbeFields();
    updateProbeReport();
  }

  function selectedProbe() {
    if (!state.probes) return null;
    const type = el.probeEditType.value === "fluid" ? "fluid" : "marker";
    const items = type === "marker" ? state.probes.markers : state.probes.fluids;
    const index = Math.trunc(Number(el.probeEditIndex.value));
    if (!Number.isFinite(index) || index < 0 || index >= items.length) return null;
    return { type, items, index, probe: items[index] };
  }

  function fillSelectedProbeFields() {
    const selected = selectedProbe();
    if (!selected) {
      [el.probeEditX, el.probeEditY, el.probeEditZ].forEach((input) => { input.value = ""; });
      el.probeEditReference.value = "";
      requestDraw();
      return;
    }
    const probe = selected.probe;
    if (selected.type === "marker") {
      el.probeEditBody.value = String(probe.body);
      el.probeEditReference.value = String(probe.reference);
    }
    el.probeEditX.value = formatControlNumber(probe.point[0]);
    el.probeEditY.value = formatControlNumber(probe.point[1]);
    el.probeEditZ.value = formatControlNumber(probe.point[2]);
    requestDraw();
  }

  function beginProbeEditing() {
    const selected = selectedProbe();
    if (!selected) return;
    state.probeEditing = true;
    state.probeTarget = null;
    if (selected.type === "marker") previewSelectedMarkerReference();
    updateProbeReport();
    requestDraw();
  }

  function stopProbeEditing() {
    state.probeEditing = false;
    state.probeTarget = null;
    state.probeResolveRequest += 1;
    if (el.moveProbeToReference) el.moveProbeToReference.disabled = true;
    requestDraw();
  }

  async function previewSelectedMarkerReference() {
    const selected = selectedProbe();
    if (!selected || selected.type !== "marker") {
      stopProbeEditing();
      return null;
    }
    state.probeEditing = true;
    state.probeTarget = null;
    el.moveProbeToReference.disabled = true;
    const bodyId = Math.max(1, Math.trunc(numValue(el.probeEditBody, selected.probe.body || 1)));
    const reference = Math.max(1, Math.trunc(numValue(el.probeEditReference, selected.probe.reference || 1)));
    const requestId = ++state.probeResolveRequest;
    requestDraw();
    try {
      const result = await postJson("/api/probes/resolve", {
        case_dir: el.caseDir.value.trim(),
        body_id: bodyId,
        reference,
      });
      if (requestId !== state.probeResolveRequest || !state.probeEditing) return null;
      state.probeTarget = {
        body: bodyId,
        reference: result.reference,
        source: result.source || "node",
        point: vector3(result.point),
      };
      el.moveProbeToReference.disabled = false;
      updateProbeReport();
      requestDraw();
      return state.probeTarget;
    } catch (err) {
      if (requestId === state.probeResolveRequest) {
        state.probeTarget = null;
        el.moveProbeToReference.disabled = true;
        requestDraw();
        setStatus(`Reference preview failed: ${cleanErrorMessage(err)}`);
      }
      return null;
    }
  }

  async function moveSelectedProbeToReference() {
    const selected = selectedProbe();
    if (!selected || selected.type !== "marker") return;
    state.probeEditing = true;
    const target = state.probeTarget || await previewSelectedMarkerReference();
    if (!target) return;
    selected.probe.body = target.body;
    selected.probe.reference = target.reference;
    selected.probe.source = target.source;
    selected.probe.point = target.point.slice();
    refreshProbeCounts();
    renderProbePanel();
    recomputeBounds();
    requestDraw();
    setStatus(`Moved marker probe ${selected.index + 1} to body ${target.body}, ${target.source} ${target.reference}. Save to write probe_in.dat.`);
  }

  async function generateProbePreview() {
    if (!state.surface || !state.surface.bodies.length) {
      setStatus("Automatic probe generation requires a loaded surface.");
      return;
    }
    try {
      const result = await postJson("/api/probes/generate", {
        case_dir: el.caseDir.value.trim(),
        body_id: Math.max(1, Math.trunc(numValue(el.probeGenerateBody, 1))),
        plane_axis: el.probePlaneAxis.value || "z",
        plane_value: numValue(el.probePlaneValue, 0),
        n_samples: Math.max(1, Math.trunc(numValue(el.probeSamples, 30))),
        plane_tolerance: Math.max(0, numValue(el.probeTolerance, 0.02)),
        x_band_factor: Math.max(0.001, numValue(el.probeBandFactor, 0.25)),
        sides: el.probeSides.value || "both",
        deduplicate: el.probeDeduplicate.checked,
        preserve_fluids: true,
      });
      state.probes = normalizeProbes(result);
      state.probes.preview = true;
      stopProbeEditing();
      setProbeLayerAvailable(true);
      el.showProbes.checked = true;
      renderProbePanel();
      recomputeBounds();
      requestDraw();
      const quality = state.probes.generation
        ? ` Max slice error ${formatShort(state.probes.generation.max_plane_error || 0)}, max X error ${formatShort(state.probes.generation.max_x_error || 0)}.`
        : "";
      setStatus(`Probe preview generated: ${state.probes.markerCount} marker, ${state.probes.fluidCount} fluid.${quality} Save to write probe_in.dat.`);
    } catch (err) {
      setStatus(`Probe generation failed: ${cleanErrorMessage(err)}`);
    }
  }

  async function applySelectedProbePosition() {
    const selected = selectedProbe();
    if (!selected) return;
    state.probeEditing = true;
    const point = [numValue(el.probeEditX), numValue(el.probeEditY), numValue(el.probeEditZ)];
    try {
      if (selected.type === "fluid") {
        selected.probe.point = point;
        state.probeTarget = null;
        setStatus(`Updated fluid probe ${selected.index + 1}. Save to write probe_in.dat.`);
      } else {
        const bodyId = Math.max(1, Math.trunc(numValue(el.probeEditBody, selected.probe.body || 1)));
        const result = await postJson("/api/probes/snap", {
          case_dir: el.caseDir.value.trim(),
          body_id: bodyId,
          point,
        });
        selected.probe.body = bodyId;
        selected.probe.reference = result.reference;
        selected.probe.point = vector3(result.point);
        selected.probe.source = "node";
        state.probeTarget = {
          body: bodyId,
          reference: result.reference,
          source: "node",
          point: vector3(result.point),
        };
        setStatus(`Marker probe ${selected.index + 1} snapped to body ${bodyId}, node ${result.reference} (distance ${formatShort(result.distance)}).`);
      }
      refreshProbeCounts();
      renderProbePanel();
      recomputeBounds();
      requestDraw();
    } catch (err) {
      setStatus(`Probe position update failed: ${cleanErrorMessage(err)}`);
    }
  }

  async function addMarkerProbe() {
    if (!state.surface || !state.surface.bodies.length) {
      setStatus("Adding a marker probe requires a loaded surface.");
      return;
    }
    const probes = editableProbes();
    const bodyId = Math.max(1, Math.trunc(numValue(el.probeEditBody, 1)));
    const bounds = bodyBounds(state.surface.bodies[Math.min(bodyId - 1, state.surface.bodies.length - 1)]);
    const point = [0, 1, 2].map((axis) => 0.5 * (bounds.min[axis] + bounds.max[axis]));
    try {
      const result = await postJson("/api/probes/snap", { case_dir: el.caseDir.value.trim(), body_id: bodyId, point });
      probes.markers.push({
        index: probes.markers.length + 1,
        body: bodyId,
        reference: result.reference,
        source: "node",
        point: vector3(result.point),
      });
      refreshProbeCounts();
      state.probeEditing = true;
      state.probeTarget = {
        body: bodyId,
        reference: result.reference,
        source: "node",
        point: vector3(result.point),
      };
      el.probeEditType.value = "marker";
      renderProbePanel();
      el.probeEditIndex.value = String(probes.markers.length - 1);
      fillSelectedProbeFields();
      setProbeLayerAvailable(true);
      el.showProbes.checked = true;
      setStatus("Marker probe added at the nearest surface node. Adjust XYZ and apply if needed.");
    } catch (err) {
      setStatus(`Add marker probe failed: ${cleanErrorMessage(err)}`);
    }
  }

  function addFluidProbe() {
    const probes = editableProbes();
    const point = [numValue(el.probeEditX), numValue(el.probeEditY), numValue(el.probeEditZ)];
    probes.fluids.push({ index: probes.fluids.length + 1, point });
    refreshProbeCounts();
    state.probeEditing = true;
    state.probeTarget = null;
    el.probeEditType.value = "fluid";
    renderProbePanel();
    el.probeEditIndex.value = String(probes.fluids.length - 1);
    fillSelectedProbeFields();
    setProbeLayerAvailable(true);
    el.showProbes.checked = true;
    recomputeBounds();
    requestDraw();
    setStatus("Fluid probe added. Edit XYZ, then save probe_in.dat.");
  }

  function deleteSelectedProbe() {
    const selected = selectedProbe();
    if (!selected) return;
    selected.items.splice(selected.index, 1);
    stopProbeEditing();
    refreshProbeCounts();
    renderProbePanel();
    recomputeBounds();
    requestDraw();
    setStatus(`Deleted ${selected.type} probe ${selected.index + 1}. Save to update probe_in.dat.`);
  }

  async function saveProbes() {
    const probes = editableProbes();
    try {
      const result = await postJson("/api/probes/save", {
        case_dir: el.caseDir.value.trim(),
        markers: probes.markers.map((probe) => ({ body: probe.body, reference: probe.reference })),
        fluids: probes.fluids.map((probe) => ({ point: probe.point })),
      });
      state.probes = normalizeProbes(result);
      addLoadedFile("probes", "probe_in.dat", "case probes");
      setProbeLayerAvailable(true);
      el.showProbes.checked = true;
      renderLoadedFiles();
      renderProbePanel();
      recomputeBounds();
      requestDraw();
      setStatus(`Saved probe_in.dat: ${state.probes.markerCount} marker, ${state.probes.fluidCount} fluid.`);
    } catch (err) {
      setStatus(`Save probes failed: ${cleanErrorMessage(err)}`);
    }
  }

  function refreshProbeCounts() {
    if (!state.probes) return;
    state.probes.markers.forEach((probe, index) => { probe.index = index + 1; });
    state.probes.fluids.forEach((probe, index) => { probe.index = index + 1; });
    state.probes.markerCount = state.probes.markers.length;
    state.probes.fluidCount = state.probes.fluids.length;
    state.probes.plottedMarkerCount = state.probes.markers.length;
    state.probes.unmatchedMarkerCount = 0;
  }

  function updateProbeReport() {
    if (!el.probeReport) return;
    if (!state.probes) {
      el.probeReport.textContent = "No probe_in.dat loaded. Generate probes or add one manually.";
      return;
    }
    const lines = [
      `marker probes : ${state.probes.markers.length}`,
      `fluid probes  : ${state.probes.fluids.length}`,
      `state         : ${state.probes.preview ? "preview (not saved)" : (state.probes.exists ? "loaded" : "new")}`,
    ];
    if (state.probes.generation) {
      const generation = state.probes.generation;
      lines.push(`slice error   : max ${formatShort(generation.max_plane_error || 0)}, mean ${formatShort(generation.mean_plane_error || 0)}`);
      lines.push(`X error       : max ${formatShort(generation.max_x_error || 0)}, mean ${formatShort(generation.mean_x_error || 0)}`);
    }
    if (state.probeEditing) {
      const selected = selectedProbe();
      if (selected) lines.push(`editing       : ${selected.type} probe ${selected.index + 1} (orange)`);
      if (state.probeTarget) {
        lines.push(`target        : body ${state.probeTarget.body}, ${state.probeTarget.source} ${state.probeTarget.reference} (blue)`);
      }
    }
    state.probes.errors.forEach((error) => lines.push(`warning       : ${error}`));
    el.probeReport.textContent = lines.join("\n");
  }

  async function previewSetupSync() {
    try {
      await requireSetupSyncApi();
      const result = await postJson("/api/setup-sync/plan", setupSyncPayload());
      showSetupSyncResult(result);
    } catch (err) {
      showSetupSyncError(`Setup sync preview failed: ${cleanErrorMessage(err)}`);
    }
  }

  async function applySetupSync() {
    try {
      await requireSetupSyncApi();
      const result = await postJson("/api/setup-sync/apply", setupSyncPayload());
      showSetupSyncResult(result);
      if (result.applied) {
        await loadCase();
        showSetupSyncResult(result);
      }
    } catch (err) {
      showSetupSyncError(`Setup sync failed: ${cleanErrorMessage(err)}`);
    }
  }

  function setupSyncPayload() {
    return {
      case_dir: el.caseDir.value.trim(),
      profile: el.syncProfile.value || "picar-current",
      fort_start: Math.max(1, Math.trunc(numValue(el.syncFortStart, 41))),
    };
  }

  function showSetupSyncResult(result) {
    const report = result.report || "No sync report returned.";
    if (el.setupSyncReport) el.setupSyncReport.textContent = report;
    const action = result.applied ? "Setup synchronized." : (result.blocked ? "Setup sync blocked." : "Setup sync ready.");
    setStatus(`${action}\n\n${report}`);
  }

  function showSetupSyncError(message) {
    if (el.setupSyncReport) el.setupSyncReport.textContent = message;
    setStatus(message);
  }

  function renderFortPanel() {
    if (!el.fortList || !el.fortBody) return;
    const fort = state.fort || { body_count: state.surface ? state.surface.bodies.length : 0, files: [] };
    const files = fort.files || [];
    if (!files.length) {
      const detail = fort.error ? `Fort report failed: ${fort.error}` : `No fort.* files found in ${el.caseDir.value.trim() || "case directory"}`;
      el.fortList.innerHTML = `<div class="item-row"><span class="item-meta">${escapeHtml(detail)}</span></div>`;
    } else {
      el.fortList.innerHTML = files.map((item) => {
        const status = item.ok
          ? `${item.frames} frames, ${item.nodes} nodes${item.node_match === false ? " | node mismatch" : ""}`
          : `invalid: ${item.error || "cannot read"}`;
        return `
          <div class="item-row">
            <div class="item-main" title="${escapeHtml(item.path)}">Body ${item.body}: ${escapeHtml(item.name)}<br><span class="item-meta">${escapeHtml(status)}</span></div>
            <div class="item-actions">
              <button type="button" data-preview-fort="${escapeHtml(item.body)}">Preview</button>
              <button type="button" data-remove-fort="${escapeHtml(item.body)}">Remove</button>
            </div>
          </div>
        `;
      }).join("");
      el.fortList.querySelectorAll("[data-preview-fort]").forEach((button) => {
        button.addEventListener("click", () => previewFortBody(Number(button.dataset.previewFort)));
      });
      el.fortList.querySelectorAll("[data-remove-fort]").forEach((button) => {
        button.addEventListener("click", () => removeFortBody(Number(button.dataset.removeFort)));
      });
    }

    const bodyIds = files.length
      ? files.map((item) => Number(item.body)).filter((value) => Number.isFinite(value) && value > 0)
      : Array.from({ length: Number(fort.body_count || 0) }, (_, i) => i + 1);
    const current = Number(el.fortBody.value) || bodyIds[0] || 1;
    el.fortBody.innerHTML = bodyIds.length
      ? bodyIds.map((id) => `<option value="${id}">Body ${id}</option>`).join("")
      : `<option value="1">Body 1</option>`;
    el.fortBody.value = bodyIds.includes(current) ? String(current) : String(bodyIds[0] || 1);
  }

  async function previewFortMotion() {
    try {
      await requireFortPreviewApi();
      const result = await postJson("/api/fort/preview", {
        case_dir: el.caseDir.value.trim(),
        body_id: Number(el.fortBody.value || 1),
        frame: Number(el.fortFrame.value || -1),
        samples: Number(el.fortSamples.value || 24),
        component_order: el.fortOrder.value || "xyz",
        motion_mode: el.fortMode.value || "velocity",
      });
      state.motion = {
        bodyId: result.body_id,
        nodeCount: result.node_count,
        frame: result.frame,
        frames: result.frames.map((frame) => ({
          frame: frame.frame,
          time: frame.time,
          highlight: frame.highlight,
          points: Float64Array.from(frame.points),
        })),
        info: result.info,
      };
      recomputeBounds();
      fit();
      setStatus(`Fort preview body ${result.body_id}, frame ${result.frame}, ${result.frames.length} sampled snapshots.`);
    } catch (err) {
      state.motion = null;
      requestDraw();
      setStatus(`Fort preview failed: ${cleanErrorMessage(err)}`);
    }
  }

  function clearFortMotion() {
    state.motion = null;
    recomputeBounds();
    requestDraw();
    updateStats();
  }

  async function previewFortBody(bodyId) {
    if (!Number.isFinite(bodyId) || bodyId <= 0) {
      setStatus("Invalid fort body id.");
      return;
    }
    el.fortBody.value = String(bodyId);
    await previewFortMotion();
  }

  async function removeFortBody(bodyId) {
    if (!Number.isFinite(bodyId) || bodyId <= 0) {
      setStatus("Invalid fort body id.");
      return;
    }
    const fortStart = state.fort && state.fort.fort_start ? state.fort.fort_start : 41;
    const fortName = `fort.${fortStart + bodyId - 1}`;
    if (!window.confirm(`Remove ${fortName} and shift later fort files down?`)) return;
    try {
      const result = await postJson("/api/fort/remove", {
        case_dir: el.caseDir.value.trim(),
        body_ids: [bodyId],
        fort_start: fortStart,
      });
      if (state.motion && Number(state.motion.bodyId) >= bodyId) {
        state.motion = null;
      }
      await loadCase();
      const removed = result.removed && result.removed.length ? result.removed.map((item) => item.name).join(", ") : "none";
      const moved = result.moved && result.moved.length
        ? result.moved.map((item) => `${item.from_name} -> ${item.to_name}`).join(", ")
        : "none";
      setStatus(`Removed fort files: ${removed}\nShifted fort files: ${moved}`);
    } catch (err) {
      setStatus(`Remove fort failed: ${cleanErrorMessage(err)}`);
    }
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

  async function requireFortPreviewApi() {
    const health = await fetchJson("/api/health");
    if (!health.fort_preview) {
      throw new Error("Backend is still running an old API. Stop the console server and restart `python -B picar_console.py` before previewing fort motion.");
    }
  }

  async function requireSetupSyncApi() {
    const health = await fetchJson("/api/health");
    if (!health.setup_sync) {
      throw new Error("Backend is still running an old API. Stop the console server and restart `python -B picar_console.py` before syncing setup.");
    }
  }

  function backendSupportsFort(report) {
    return !!(report && report.fort);
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
    if (panelId !== "probePanel") stopProbeEditing();
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
      state.mesh.z = params.Lz > 0 ? makeAxisNodesFromControls("z") : null;
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
    const denseSizes = uniformSizes(Math.max(0, cfg.denseEnd - cfg.denseStart), cfg.denseCount);
    const leftUniformSizes = uniformSizes(Math.max(0, cfg.leftLayerLength), cfg.leftUniform);
    const rightUniformSizes = uniformSizes(Math.max(0, cfg.rightLayerLength), cfg.rightUniform);
    const denseSpacing = denseSizes.length ? denseSizes[0] : 0;
    const leftAdjacent = leftUniformSizes.length ? leftUniformSizes[0] : denseSpacing;
    const rightAdjacent = rightUniformSizes.length ? rightUniformSizes[0] : denseSpacing;
    const sizes = [
      ...smoothStretchSizes(Math.max(0, cfg.denseStart - cfg.start - cfg.leftLayerLength), cfg.leftStretch, leftAdjacent, "left"),
      ...leftUniformSizes,
      ...denseSizes,
      ...rightUniformSizes,
      ...smoothStretchSizes(Math.max(0, cfg.end - cfg.denseEnd - cfg.rightLayerLength), cfg.rightStretch, rightAdjacent, "right"),
    ];
    const nodes = [cfg.start];
    sizes.forEach((size) => nodes.push(nodes[nodes.length - 1] + size));
    if (nodes.length === 1) nodes.push(cfg.end);
    nodes[nodes.length - 1] = cfg.end;
    return Float64Array.from(nodes);
  }

  function uniformSizes(length, count) {
    if (count <= 0 || length <= 0) return [];
    return Array(count).fill(length / count);
  }

  function smoothStretchSizes(length, count, adjacentSize, side) {
    if (count <= 0 || length <= 0) return [];
    if (adjacentSize <= 0 || length <= adjacentSize * count) return uniformSizes(length, count);
    const makeSizes = (growth) => {
      const sizes = [];
      let previous = adjacentSize;
      for (let i = 1; i <= count; i += 1) {
        previous = side === "left"
          ? previous / (1 - i * growth)
          : previous * (1 + i * growth);
        sizes.push(previous);
      }
      return sizes;
    };
    let lo = 0;
    let hi = side === "left" ? (1 - 1e-14) / count : 1;
    const sum = (items) => items.reduce((acc, value) => acc + value, 0);
    while (side === "right" && sum(makeSizes(hi)) < length) hi *= 2;
    for (let iter = 0; iter < 100; iter += 1) {
      const mid = 0.5 * (lo + hi);
      if (sum(makeSizes(mid)) < length) lo = mid;
      else hi = mid;
    }
    const sizes = makeSizes(0.5 * (lo + hi));
    return side === "left" ? sizes.reverse() : sizes;
  }

  async function saveMeshInput() {
    try {
      const result = await postJson("/api/mesh/save", { case_dir: el.caseDir.value.trim(), params: readMeshParams() });
      previewMeshFromControls();
      setStatus(`Mesh input saved: ${result.path || "mesh_input_twolayers.dat"}`);
    } catch (err) {
      setStatus(`Save mesh input failed: ${err.message || err}`);
    }
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
      setStatus(result.mesh && result.mesh.z.length ? "xgrid/ygrid/zgrid generated." : "xgrid/ygrid generated; set a positive Z range to write zgrid.dat.");
    } catch (err) {
      setStatus(`Generate XYZ failed: ${err.message || err}`);
    }
  }

  async function importGeometry(append, explicitFile = null) {
    const file = explicitFile || (el.geometryFile.files && el.geometryFile.files[0]) || state.pendingGeometryFile;
    if (!file) {
      setStatus("Choose or drop a .stl or .dat file first.");
      return false;
    }
    try {
      const lower = file.name.toLowerCase();
      if (lower.endsWith(".dat")) {
        if (append) {
          setStatus("Append supports STL files. Use Import to replace the surface with a DAT file.");
          return false;
        }
        setStatus(`Importing surface: ${file.name}`);
        const content = await file.text();
        await postJson("/api/geometry/save-surface", { case_dir: el.caseDir.value.trim(), content });
      } else if (lower.endsWith(".stl")) {
        setStatus(`Importing STL: ${file.name}`);
        const contentBase64 = await fileToBase64(file);
        await postJson("/api/geometry/import-stl", {
          case_dir: el.caseDir.value.trim(),
          filename: file.name,
          content_base64: contentBase64,
          append,
        });
      } else {
        setStatus("Geometry import supports .stl and .dat.");
        return false;
      }
      await loadCase();
      state.pendingGeometryFile = null;
      renderLoadedFiles();
      renderBodyList();
      setStatus(append ? "Geometry appended." : "Geometry imported.");
      return true;
    } catch (err) {
      setStatus(`Geometry import failed: ${err.message || err}`);
      return false;
    }
  }

  async function exportStl() {
    try {
      const ids = selectedBodyIds();
      const result = await postJson("/api/geometry/export-stl", {
        case_dir: el.caseDir.value.trim(),
        output: "surface_export.stl",
        body_ids: ids,
      });
      const selected = ids.length ? ` bodies ${ids.join(", ")}` : "";
      setStatus(`STL exported${selected}: ${result.path}`);
    } catch (err) {
      setStatus(`STL export failed: ${err.message || err}`);
    }
  }

  function exportPlotJson() {
    try {
      const payload = buildPlotExport();
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
      downloadBlob(blob, `picar_plot_${timestampForFilename()}.json`);
      setStatus("Plot JSON exported.");
    } catch (err) {
      setStatus(`Plot JSON export failed: ${err.message || err}`);
    }
  }

  function exportPlotPng() {
    try {
      draw();
      if (!el.viewport.toBlob) {
        throw new Error("Canvas PNG export is not supported by this browser.");
      }
      el.viewport.toBlob((blob) => {
        if (!blob) {
          setStatus("Plot PNG export failed: empty canvas image.");
          return;
        }
        downloadBlob(blob, `picar_plot_${timestampForFilename()}.png`);
        setStatus("Plot PNG exported.");
      }, "image/png");
    } catch (err) {
      setStatus(`Plot PNG export failed: ${err.message || err}`);
    }
  }

  function buildPlotExport() {
    return {
      version: 1,
      exported_at: new Date().toISOString(),
      case_dir: el.caseDir.value.trim(),
      canvas: {
        width: el.viewport.width,
        height: el.viewport.height,
        css_width: Math.round(el.viewport.getBoundingClientRect().width),
        css_height: Math.round(el.viewport.getBoundingClientRect().height),
        device_pixel_ratio: window.devicePixelRatio || 1,
      },
      view: {
        mode: state.viewMode,
        angle_x: state.angleX,
        angle_y: state.angleY,
        zoom: state.zoom,
        pan_x: state.panX,
        pan_y: state.panY,
        bounds: state.bounds ? {
          min: state.bounds.min.slice(),
          max: state.bounds.max.slice(),
          span: state.bounds.span,
        } : null,
      },
      layers: {
        surface_points: el.showSurfacePoints.checked,
        surface_triangles: el.showSurfaceLines.checked,
        mesh_boundary: el.showMeshBounds.checked,
        dense_region: el.showDenseRegion.checked,
        amr_regions: el.showAmrRegions.checked,
        probes: el.showProbes.checked,
        sampled_grid: el.showFullMesh.checked,
        fort_motion: el.showFortMotion.checked,
        axes_and_ticks: el.showAxes.checked,
      },
      data: {
        surface: serializeSurface(state.surface),
        mesh: serializeMesh(state.mesh),
        amr: state.amr || null,
        probes: state.probes || null,
        fort: state.fort || null,
        motion: serializeMotion(state.motion),
      },
    };
  }

  function serializeSurface(surface) {
    if (!surface) return null;
    return {
      bodies: surface.bodies.map((body, bodyIndex) => ({
        body_id: bodyIndex + 1,
        node_count: body.nodeCount,
        elem_count: body.elemCount,
        points: arrayToList(body.points),
        elems: arrayToList(body.elems),
      })),
    };
  }

  function serializeMesh(mesh) {
    return {
      x: mesh.x ? arrayToList(mesh.x) : null,
      y: mesh.y ? arrayToList(mesh.y) : null,
      z: mesh.z ? arrayToList(mesh.z) : null,
      dense_box: mesh.denseBox || null,
    };
  }

  function serializeMotion(motion) {
    if (!motion) return null;
    return {
      body_id: motion.bodyId,
      node_count: motion.nodeCount,
      frame: motion.frame,
      info: motion.info || null,
      frames: motion.frames.map((frame) => ({
        frame: frame.frame,
        time: frame.time,
        highlight: frame.highlight,
        points: arrayToList(frame.points),
      })),
    };
  }

  function arrayToList(values) {
    return Array.prototype.slice.call(values || []);
  }

  function downloadBlob(blob, filename) {
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  }

  function timestampForFilename() {
    return new Date().toISOString().replace(/[:.]/g, "-");
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

  function parseAmrText(text) {
    let resize = 0;
    const layers = [];
    let currentLayer = null;
    let expectedBlocks = null;
    text.split(/\r?\n/).forEach((rawLine) => {
      const line = rawLine.trim();
      if (!line) return;
      const numbers = Array.from(numericTokens(line));
      if (line.includes("AMR_RESIZE") && numbers.length) {
        resize = Math.trunc(numbers[0]);
        return;
      }
      if (line.includes("AMR Layer")) {
        currentLayer = { layer: numbers.length ? Math.trunc(numbers[numbers.length - 1]) : layers.length + 1, blocks: [] };
        layers.push(currentLayer);
        expectedBlocks = null;
        return;
      }
      if (!currentLayer) return;
      if (expectedBlocks === null && numbers.length === 1) {
        expectedBlocks = Math.trunc(numbers[0]);
        return;
      }
      if (numbers.length < 9) return;
      currentLayer.blocks.push({
        id: Math.trunc(numbers[0]),
        parent: Math.trunc(numbers[1]),
        start: [numbers[2], numbers[3], numbers[4]],
        end: [numbers[5], numbers[6], numbers[7]],
        moving: Math.trunc(numbers[8]),
      });
      if (expectedBlocks !== null && currentLayer.blocks.length >= expectedBlocks) expectedBlocks = null;
    });
    return normalizeAmr({ resize, layers });
  }

  function normalizeAmr(amr) {
    const rawLayers = Array.isArray(amr && amr.layers) ? amr.layers : [];
    return {
      ok: amr && amr.ok !== false,
      path: amr && amr.path ? String(amr.path) : "",
      resize: Math.trunc(Number(amr && amr.resize) || 0),
      layers: rawLayers.map((layer, layerIndex) => ({
        layer: Math.trunc(Number(layer.layer) || layerIndex + 1),
        blocks: Array.isArray(layer.blocks) ? layer.blocks.map((block) => ({
          id: Math.trunc(Number(block.id) || 0),
          parent: Math.trunc(Number(block.parent) || 0),
          start: vector3(block.start),
          end: vector3(block.end),
          moving: Math.trunc(Number(block.moving) || 0),
        })) : [],
      })),
    };
  }

  function normalizeProbes(probes) {
    const rawMarkers = Array.isArray(probes && probes.markers) ? probes.markers : [];
    const rawFluids = Array.isArray(probes && probes.fluids) ? probes.fluids : [];
    return {
      ok: probes && probes.ok !== false,
      exists: probes && probes.exists !== false,
      path: probes && probes.path ? String(probes.path) : "",
      markerCount: Math.trunc(Number(probes && probes.marker_count) || rawMarkers.length),
      fluidCount: Math.trunc(Number(probes && probes.fluid_count) || rawFluids.length),
      plottedMarkerCount: Math.trunc(Number(probes && probes.plotted_marker_count) || rawMarkers.length),
      unmatchedMarkerCount: Math.trunc(Number(probes && probes.unmatched_marker_count) || 0),
      preview: !!(probes && probes.preview),
      generation: probes && probes.generation && typeof probes.generation === "object"
        ? probes.generation
        : null,
      errors: Array.isArray(probes && probes.errors) ? probes.errors.map(String) : [],
      markers: rawMarkers.map((marker, markerIndex) => ({
        index: Math.trunc(Number(marker.index) || markerIndex + 1),
        body: Math.trunc(Number(marker.body) || 0),
        reference: Math.trunc(Number(marker.reference) || 0),
        source: marker.source ? String(marker.source) : "marker",
        point: vector3(marker.point),
      })),
      fluids: rawFluids.map((probe, probeIndex) => ({
        index: Math.trunc(Number(probe.index) || probeIndex + 1),
        point: vector3(probe.point),
      })),
    };
  }

  function setProbeLayerAvailable(available) {
    if (!el.showProbes) return;
    el.showProbes.disabled = !available;
    if (el.probeLayerControl) {
      el.probeLayerControl.classList.toggle("disabled", !available);
      el.probeLayerControl.title = available ? "" : "No probe_in.dat detected for this case";
    }
    if (!available) el.showProbes.checked = false;
  }

  function vector3(value) {
    const raw = Array.isArray(value) ? value : [];
    return [Number(raw[0]) || 0, Number(raw[1]) || 0, Number(raw[2]) || 0];
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
    if (el.showAmrRegions.checked) drawAmrRegions(ctx, rect);
    if (el.showFullMesh.checked) drawSampledGrid(ctx, rect);
    drawSurface(ctx, rect);
    drawFortMotion(ctx, rect);
    drawProbes(ctx, rect);
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

  function drawFortMotion(ctx, rect) {
    if (!el.showFortMotion.checked || !state.motion || !state.surface) return;
    const body = state.surface.bodies[state.motion.bodyId - 1];
    if (!body) return;
    state.motion.frames.forEach((frame) => {
      drawMotionFramePoints(ctx, rect, body, frame.points, frame.highlight);
    });
  }

  function drawMotionFramePoints(ctx, rect, body, points, highlight) {
    ctx.save();
    ctx.globalAlpha = highlight ? 0.92 : 0.16;
    ctx.fillStyle = highlight ? "#d62828" : "#7d858d";
    const radius = highlight ? 1.15 : 0.65;
    for (let i = 0; i < body.nodeCount; i += 1) {
      const offset = i * 3;
      if (offset + 2 >= points.length) break;
      const p = projectPoint(rect, points[offset], points[offset + 1], points[offset + 2]);
      ctx.fillRect(p.x - radius, p.y - radius, radius * 2, radius * 2);
    }
    ctx.restore();
  }

  function drawProbes(ctx, rect) {
    if (!el.showProbes.checked || !state.probes) return;
    const markers = sample(state.probes.markers, MAX_DRAWN_PROBES);
    const fluids = sample(state.probes.fluids, MAX_DRAWN_PROBES);

    ctx.save();
    ctx.globalAlpha = 0.82;
    markers.forEach((probe) => {
      const p = projectPoint(rect, probe.point[0], probe.point[1], probe.point[2]);
      drawProbeMarker(ctx, p, "#b11654");
    });
    fluids.forEach((probe) => {
      const p = projectPoint(rect, probe.point[0], probe.point[1], probe.point[2]);
      drawFluidProbe(ctx, p, "#0f7b68");
    });
    const selected = state.probeEditing ? selectedProbe() : null;
    if (selected) {
      const p = projectPoint(rect, selected.probe.point[0], selected.probe.point[1], selected.probe.point[2]);
      ctx.lineWidth = 2;
      ctx.strokeStyle = "#f59f00";
      ctx.beginPath();
      ctx.arc(p.x, p.y, 7, 0, Math.PI * 2);
      ctx.stroke();
    }
    if (state.probeEditing && state.probeTarget) {
      const target = state.probeTarget;
      const p = projectPoint(rect, target.point[0], target.point[1], target.point[2]);
      drawProbeEditTarget(ctx, p, "#1976d2");
    }
    ctx.restore();
  }

  function drawProbeEditTarget(ctx, point, color) {
    const radius = 5;
    ctx.lineWidth = 2;
    ctx.strokeStyle = color;
    ctx.beginPath();
    ctx.moveTo(point.x, point.y - radius);
    ctx.lineTo(point.x + radius, point.y);
    ctx.lineTo(point.x, point.y + radius);
    ctx.lineTo(point.x - radius, point.y);
    ctx.closePath();
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(point.x - radius - 2, point.y);
    ctx.lineTo(point.x + radius + 2, point.y);
    ctx.moveTo(point.x, point.y - radius - 2);
    ctx.lineTo(point.x, point.y + radius + 2);
    ctx.stroke();
  }

  function drawProbeMarker(ctx, point, color) {
    ctx.lineWidth = 1.1;
    ctx.strokeStyle = "#ffffff";
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(point.x, point.y, 2.4, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.strokeStyle = color;
    ctx.beginPath();
    ctx.arc(point.x, point.y, 3.8, 0, Math.PI * 2);
    ctx.stroke();
  }

  function drawFluidProbe(ctx, point, color) {
    const radius = 3.4;
    ctx.lineWidth = 1.1;
    ctx.strokeStyle = "#ffffff";
    ctx.beginPath();
    ctx.moveTo(point.x - radius, point.y);
    ctx.lineTo(point.x + radius, point.y);
    ctx.moveTo(point.x, point.y - radius);
    ctx.lineTo(point.x, point.y + radius);
    ctx.stroke();
    ctx.strokeStyle = color;
    ctx.beginPath();
    ctx.moveTo(point.x - radius, point.y);
    ctx.lineTo(point.x + radius, point.y);
    ctx.moveTo(point.x, point.y - radius);
    ctx.lineTo(point.x, point.y + radius);
    ctx.stroke();
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

  function drawAmrRegions(ctx, rect) {
    if (!state.amr || !state.amr.layers.length) return;
    state.amr.layers.forEach((layer, layerIndex) => {
      const color = amrColor(layerIndex);
      layer.blocks.forEach((block) => {
        const box = amrBlockBox(block);
        drawBoxFaces(ctx, rect, box, amrFillColor(color));
        drawBoxEdges(ctx, rect, box, color, 1.5);
      });
    });
  }

  function amrBlockBox(block) {
    return {
      x0: Math.min(block.start[0], block.end[0]),
      x1: Math.max(block.start[0], block.end[0]),
      y0: Math.min(block.start[1], block.end[1]),
      y1: Math.max(block.start[1], block.end[1]),
      z0: Math.min(block.start[2], block.end[2]),
      z1: Math.max(block.start[2], block.end[2]),
    };
  }

  function amrColor(index) {
    return AMR_COLORS[index % AMR_COLORS.length];
  }

  function amrFillColor(color) {
    const hex = color.replace("#", "");
    const r = parseInt(hex.slice(0, 2), 16);
    const g = parseInt(hex.slice(2, 4), 16);
    const b = parseInt(hex.slice(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, 0.12)`;
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
    if (state.motion) {
      state.motion.frames.forEach((frame) => {
        for (let i = 0; i < frame.points.length; i += 3) add(frame.points[i], frame.points[i + 1], frame.points[i + 2]);
      });
    }
    if (state.probes) {
      state.probes.markers.forEach((probe) => add(probe.point[0], probe.point[1], probe.point[2]));
      state.probes.fluids.forEach((probe) => add(probe.point[0], probe.point[1], probe.point[2]));
    }
    if (state.amr) {
      state.amr.layers.forEach((layer) => {
        layer.blocks.forEach((block) => {
          const box = amrBlockBox(block);
          add(box.x0, box.y0, box.z0);
          add(box.x1, box.y1, box.z1);
        });
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
    const threshold = minSpacing + Math.max(Math.abs(minSpacing) * 1e-6, 1e-12);
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

  function resetView() {
    state.viewMode = "iso";
    state.angleX = 0.62;
    state.angleY = -0.78;
    state.zoom = 1;
    state.panX = 0;
    state.panY = 0;
    setActiveViewButton(el.isoView);
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
    event.preventDefault();
    state.dragging = true;
    state.dragMode = event.ctrlKey || isPlaneView() ? "pan" : "rotate";
    el.viewport.classList.toggle("panning", state.dragMode === "pan");
    state.lastX = event.clientX;
    state.lastY = event.clientY;
  }

  function drag(event) {
    if (!state.dragging) return;
    const dx = event.clientX - state.lastX;
    const dy = event.clientY - state.lastY;
    const shouldPan = state.dragMode === "pan" || event.ctrlKey || isPlaneView();
    el.viewport.classList.toggle("panning", shouldPan);
    if (shouldPan) {
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
    if (state.amr && state.amr.layers.length) {
      const blockCount = state.amr.layers.reduce((sum, layer) => sum + layer.blocks.length, 0);
      lines.push(`AMR layers    : ${state.amr.layers.length} layers, ${blockCount} blocks`);
    }
    if (state.probes) {
      lines.push(
        `probes        : marker ${state.probes.plottedMarkerCount}/${state.probes.markerCount}, fluid ${state.probes.fluidCount}`
      );
      if (state.probes.unmatchedMarkerCount) lines.push(`probe warnings : ${state.probes.unmatchedMarkerCount} marker probes unresolved`);
    }
    if (state.fort && state.fort.files && state.fort.files.length) {
      const okCount = state.fort.files.filter((item) => item.ok && item.node_match !== false).length;
      lines.push(`fort files    : ${okCount} / ${state.fort.files.length} matched`);
    }
    if (state.motion) {
      lines.push(`fort preview  : body ${state.motion.bodyId}, frame ${state.motion.frame}, snapshots ${state.motion.frames.length}`);
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
    if (report.fort && report.fort.files && report.fort.files.length) {
      const okCount = report.fort.files.filter((item) => item.ok && item.node_match !== false).length;
      lines.push(`fort files: ${okCount}/${report.fort.files.length} matched`);
    }
    if (report.amr && report.amr.ok) lines.push(`AMR: ${report.amr.layers.length} layers, ${report.amr.block_count || 0} blocks`);
    if (report.probes && report.probes.exists) {
      lines.push(`probes: marker ${report.probes.plotted_marker_count || 0}/${report.probes.marker_count || 0}, fluid ${report.probes.fluid_count || 0}`);
    }
    lines.push(`dense region: ${report.mesh && report.mesh.dense_box ? "available" : "not found"}`);
    lines.push(`validation: ${report.validation.length ? "FAIL" : "PASS"}`);
    report.validation.forEach((item) => lines.push(`- ${item}`));
    return lines.join("\n");
  }

  function updateCommands() {
    const caseDir = el.caseDir.value || "path/to/case";
    el.commands.textContent = [
      `python case_editor/run_case_editor.py --case-dir "${caseDir}" report`,
      `python case_editor/run_case_editor.py --case-dir "${caseDir}" sync --dry-run`,
      `python case_editor/run_case_editor.py --case-dir "${caseDir}" sync`,
      `python -m mesh.run_mesh_tools --case-dir "${caseDir}" inspect`,
      `python geometry/unstructure_surface/run_surface_tools.py --case-dir "${caseDir}" inspect --roundtrip`,
    ].join("\n\n");
  }

  async function fetchText(url) {
    const res = await fetch(url);
    const text = await res.text();
    if (!res.ok) throw new Error(readResponseError(text, res.statusText));
    return text;
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
    let data = {};
    try {
      data = text ? JSON.parse(text) : {};
    } catch {
      data = {};
    }
    if (!res.ok || data.ok === false) throw new Error(data.error || readResponseError(text, res.statusText));
    return data;
  }

  function readResponseError(text, fallback) {
    const value = String(text || "").trim();
    if (!value) return fallback || "Request failed";
    try {
      const data = JSON.parse(value);
      if (data.error) return data.error;
      if (data.message) return data.message;
    } catch {
      // Fall through to HTML/text cleanup.
    }
    const title = value.match(/<p>Message:\s*([^<]+)<\/p>/i);
    if (title) return title[1].trim();
    return value.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
  }

  function cleanErrorMessage(err) {
    return readResponseError(err && err.message ? err.message : String(err), "Request failed");
  }
}());
