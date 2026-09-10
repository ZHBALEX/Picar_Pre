(function () {
  const MAX_POINTS = 35000;
  const INTERACTIVE_POINTS = 8000;
  const MAX_GRID_LINES = 48;
  const AMR_COLORS = ["#d62828", "#2f80ed", "#f59f00", "#7b2cbf", "#2b9348", "#d9480f"];
  const el = Object.fromEntries(["source", "output", "casePrefix", "fortStart", "componentOrder", "loadBodies", "addGroup", "groups", "preview", "create", "cases", "status", "canvas", "showMeshBounds", "showDenseRegion", "showFullMesh", "showAmrRegions", "reset", "top", "iso", "xy", "xz", "yz", "fit"].map(id => [id, document.getElementById(id)]));
  const ctx = el.canvas.getContext("2d");
  const state = {
    staticBodies: [], staticAmrBlocks: [], cases: [], mesh: null, amr: null, bounds: null,
    viewMode: "iso", angleX: 0.62, angleY: -0.78, zoom: 1, panX: 0, panY: 0,
    dragging: false, dragMode: null, lastX: 0, lastY: 0, framePending: false, interactingUntil: 0,
  };

  function payload() {
    const groups = Array.from(el.groups.querySelectorAll(".group-card")).map(card => ({
      body_ids: card.querySelector("[data-field=body_ids]").value.trim(),
      x: card.querySelector("[data-field=x]").value.trim(),
      y: card.querySelector("[data-field=y]").value.trim(),
      z: card.querySelector("[data-field=z]").value.trim(),
      rx: card.querySelector("[data-field=rx]").value.trim(),
      ry: card.querySelector("[data-field=ry]").value.trim(),
      rz: card.querySelector("[data-field=rz]").value.trim(),
      amr_blocks: card.querySelector("[data-field=amr_blocks]").value.trim(),
    }));
    return { source_case: el.source.value.trim(), output_root: el.output.value.trim(), case_prefix: el.casePrefix.value.trim(), fort_start: Number(el.fortStart.value), component_order: el.componentOrder.value.trim(), groups };
  }

  async function post(path) {
    const response = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload()) });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || response.statusText);
    return result;
  }

  async function requireCurrentBackend() {
    let response;
    try {
      response = await fetch("/api/health", { cache: "no-store" });
    } catch (error) {
      throw new Error("Cannot reach the batch backend. Restart: python -B batch_console.py <source_case>");
    }
    if (!response.ok) {
      throw new Error("The batch backend is outdated. Stop it with Ctrl+C, then restart batch_console.py.");
    }
    const health = await response.json();
    if (health.api_version !== "mesh-amr-v7") {
      throw new Error(`The batch backend is outdated (${health.api_version || "unknown version"}). Stop it with Ctrl+C, then restart batch_console.py.`);
    }
  }

  async function loadBodies() {
    setStatus("Reading source bodies...");
    try {
      await requireCurrentBackend();
      const result = await post("/api/source");
      el.source.value = result.source_case;
      el.output.value = result.output_root;
      if (!el.groups.children.length) addGroup("1", "0", "0.1, 0.2, 0.3, 0.4", "0");
      state.mesh = result.mesh || null;
      state.amr = result.amr || null;
      const movingBlocks = result.amr ? result.amr.layers.flatMap(layer => layer.blocks).filter(block => Number(block.moving) !== 0).map(block => block.id) : [];
      const meshText = result.mesh ? `mesh ${result.mesh.x.length}x${result.mesh.y.length}x${Math.max(1, result.mesh.z.length)}` : "no grid";
      const amrText = `AMR ${result.amr ? result.amr.block_count || 0 : 0} blocks${movingBlocks.length ? ` (moving: ${movingBlocks.join(",")})` : ""}`;
      setStatus(`${result.bodies.length} bodies available (1-${result.bodies.length}) · ${meshText} · ${amrText}\n` + result.bodies.map(body => `Body ${body.body_id}: ${body.node_count.toLocaleString()} nodes · ${body.has_fort ? body.fort : "no fort"}`).join("\n"));
    } catch (error) {
      setStatus(error.message || String(error));
    }
  }

  function addGroup(bodyIds = "", x = "0", y = "0", z = "0", rx = "0", ry = "0", rz = "0", amrBlocks = "") {
    const card = document.createElement("div");
    card.className = "group-card";
    card.innerHTML = `<div class="group-head"><label>Body IDs<input data-field="body_ids" value="${escapeHtml(bodyIds)}" placeholder="2-4"></label><button type="button">Remove</button></div><div class="axis-grid"><label>X offsets<input data-field="x" value="${escapeHtml(x)}"></label><label>Y offsets<input data-field="y" value="${escapeHtml(y)}"></label><label>Z offsets<input data-field="z" value="${escapeHtml(z)}"></label></div><div class="axis-grid rotation-grid"><label>RX degrees<input data-field="rx" value="${escapeHtml(rx)}"></label><label>RY degrees<input data-field="ry" value="${escapeHtml(ry)}"></label><label>RZ degrees<input data-field="rz" value="${escapeHtml(rz)}"></label></div><label class="amr-follow">AMR blocks following this translation<input data-field="amr_blocks" value="${escapeHtml(amrBlocks)}" placeholder="blank, moving, all, or 1,3-4"></label>`;
    card.querySelector("button").addEventListener("click", () => card.remove());
    el.groups.appendChild(card);
  }

  async function preview() {
    setStatus("Loading point-cloud preview...");
    try {
      await requireCurrentBackend();
      const result = await post("/api/preview");
      el.source.value = result.source_case;
      el.output.value = result.output_root;
      if (!Array.isArray(result.static_bodies) || !Array.isArray(result.cases) || result.cases.some(item => !Array.isArray(item.bodies) || item.bodies.some(body => !Array.isArray(body.points)))) {
        throw new Error("Unexpected preview response. Stop the batch server with Ctrl+C and restart batch_console.py.");
      }
      state.staticBodies = result.static_bodies;
      state.staticAmrBlocks = Array.isArray(result.static_amr_blocks) ? result.static_amr_blocks : [];
      state.mesh = result.mesh || null;
      state.amr = result.amr || null;
      const count = Math.max(1, result.cases.length - 1);
      state.cases = result.cases.map((item, index) => ({ ...item, visible: true, opacity: 0.88 - 0.72 * index / count }));
      renderCaseList();
      recomputeBounds();
      fit();
      const sent = state.staticBodies.reduce((sum, body) => sum + body.points.length, 0) + state.cases.reduce((sum, item) => sum + item.bodies.reduce((bodySum, body) => bodySum + body.points.length, 0), 0);
      const pivots = (result.rotation_pivots || []).map(item => {
        const center = item.center.map(value => Number(value).toPrecision(7)).join(", ");
        const drift = Math.max(...item.forts.map(fort => fort.max_cycle_drift));
        return `Bodies ${item.body_ids.join(",")}: motion center [${center}], max cycle drift ${drift.toExponential(3)}`;
      });
      const followedAmr = state.cases.length && Array.isArray(state.cases[0].amr_blocks) ? state.cases[0].amr_blocks.length : 0;
      const environment = `${state.mesh ? "grid loaded" : "no grid"} · AMR ${state.amr ? state.amr.block_count || 0 : 0} blocks${followedAmr ? `, ${followedAmr} following each case` : ""}`;
      setStatus(`${state.cases.length} cases · ${sent.toLocaleString()} sampled points · ${environment}\n${pivots.join("\n")}\nStatic bodies and AMR are drawn once. Preview wrote no files.`);
    } catch (error) {
      setStatus(error.message || String(error));
    }
  }

  async function createCases() {
    setStatus("Creating case copies...");
    try {
      const result = await post("/api/create");
      setStatus(`Created ${result.created.length} cases:\n${result.created.join("\n")}`);
    } catch (error) {
      setStatus(error.message || String(error));
    }
  }

  function renderCaseList() {
    el.cases.replaceChildren();
    state.cases.forEach((item) => {
      const row = document.createElement("div");
      row.className = "case";
      row.innerHTML = `<input type="checkbox" checked><span>${escapeHtml(item.name)}</span><i class="swatch"></i>`;
      row.querySelector("input").addEventListener("change", event => { item.visible = event.target.checked; requestDraw(); });
      row.querySelector(".swatch").style.opacity = String(item.opacity);
      row.title = `${item.path}; opacity ${item.opacity.toFixed(2)}`;
      el.cases.appendChild(row);
    });
  }

  function recomputeBounds() {
    const min = [Infinity, Infinity, Infinity], max = [-Infinity, -Infinity, -Infinity];
    const include = body => body.points.forEach(point => { for (let i = 0; i < 3; i += 1) { min[i] = Math.min(min[i], point[i]); max[i] = Math.max(max[i], point[i]); } });
    const includePoint = point => { for (let i = 0; i < 3; i += 1) { min[i] = Math.min(min[i], point[i]); max[i] = Math.max(max[i], point[i]); } };
    const includeBox = box => { includePoint([box.x0, box.y0, box.z0]); includePoint([box.x1, box.y1, box.z1]); };
    state.staticBodies.forEach(include);
    state.cases.forEach(item => item.bodies.forEach(include));
    if ((el.showMeshBounds.checked || el.showFullMesh.checked) && meshDomainBox()) includeBox(meshDomainBox());
    if (el.showDenseRegion.checked && state.mesh && state.mesh.dense_box) includeBox(state.mesh.dense_box);
    if (el.showAmrRegions.checked) {
      state.staticAmrBlocks.forEach(block => includeBox(amrBlockBox(block)));
      state.cases.forEach(item => (item.amr_blocks || []).forEach(block => includeBox(amrBlockBox(block))));
    }
    if (!Number.isFinite(min[0])) { state.bounds = null; return; }
    for (let i = 0; i < 3; i += 1) if (Math.abs(max[i] - min[i]) < 1e-12) { min[i] -= 0.5; max[i] += 0.5; }
    state.bounds = { min, max, span: Math.max(max[0] - min[0], max[1] - min[1], max[2] - min[2]) };
  }

  function requestDraw() {
    if (state.framePending) return;
    state.framePending = true;
    requestAnimationFrame(() => { state.framePending = false; draw(); });
  }

  function draw() {
    const rect = el.canvas.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
    el.canvas.width = Math.max(1, Math.floor(rect.width * dpr));
    el.canvas.height = Math.max(1, Math.floor(rect.height * dpr));
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = "#f7f8f9";
    ctx.fillRect(0, 0, rect.width, rect.height);
    if (!state.bounds) return;
    drawBounds(rect);
    if (el.showFullMesh.checked) drawSampledGrid(rect);
    if (el.showMeshBounds.checked) drawMeshBounds(rect);
    if (el.showDenseRegion.checked) drawDenseRegion(rect);
    if (el.showAmrRegions.checked) drawAmrRegions(rect);
    state.staticBodies.forEach(body => drawPoints(rect, body.points, "#555d65", 0.52, 1.25));
    state.cases.forEach(item => { if (item.visible) item.bodies.forEach(body => drawPoints(rect, body.points, "#0e5f95", item.opacity, 1.35)); });
  }

  function drawPoints(rect, points, color, opacity, radius) {
    const budget = state.dragging || performance.now() < state.interactingUntil ? INTERACTIVE_POINTS : MAX_POINTS;
    const stride = Math.max(1, Math.ceil(points.length / budget));
    ctx.save();
    ctx.globalAlpha = opacity;
    ctx.fillStyle = color;
    ctx.beginPath();
    for (let i = 0; i < points.length; i += stride) {
      const p = project(rect, points[i]);
      ctx.rect(p.x - radius, p.y - radius, radius * 2, radius * 2);
    }
    ctx.fill();
    ctx.restore();
  }

  function drawBounds(rect) {
    const b = state.bounds;
    const corners = [[b.min[0],b.min[1],b.min[2]],[b.max[0],b.min[1],b.min[2]],[b.max[0],b.max[1],b.min[2]],[b.min[0],b.max[1],b.min[2]],[b.min[0],b.min[1],b.max[2]],[b.max[0],b.min[1],b.max[2]],[b.max[0],b.max[1],b.max[2]],[b.min[0],b.max[1],b.max[2]]];
    const edges = [[0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7]];
    ctx.strokeStyle = "rgba(100,110,120,.22)"; ctx.lineWidth = 0.8; ctx.beginPath();
    edges.forEach(([a,b]) => { const p=project(rect,corners[a]), q=project(rect,corners[b]); ctx.moveTo(p.x,p.y); ctx.lineTo(q.x,q.y); });
    ctx.stroke();
  }

  function meshDomainBox() {
    if (!state.mesh || !state.mesh.x || !state.mesh.y || !state.mesh.x.length || !state.mesh.y.length) return null;
    const z = state.mesh.z && state.mesh.z.length ? state.mesh.z : [0, 0];
    return { x0: state.mesh.x[0], x1: state.mesh.x[state.mesh.x.length - 1], y0: state.mesh.y[0], y1: state.mesh.y[state.mesh.y.length - 1], z0: z[0], z1: z[z.length - 1] };
  }

  function boxCorners(box) {
    return [[box.x0,box.y0,box.z0],[box.x1,box.y0,box.z0],[box.x1,box.y1,box.z0],[box.x0,box.y1,box.z0],[box.x0,box.y0,box.z1],[box.x1,box.y0,box.z1],[box.x1,box.y1,box.z1],[box.x0,box.y1,box.z1]];
  }

  function drawBox(rect, box, stroke, fill, width = 1) {
    const corners = boxCorners(box).map(point => project(rect, point));
    const faces = [[0,1,2,3],[4,5,6,7],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7]];
    const edges = [[0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7]];
    if (fill) {
      ctx.fillStyle = fill;
      faces.forEach(face => { ctx.beginPath(); ctx.moveTo(corners[face[0]].x, corners[face[0]].y); face.slice(1).forEach(i => ctx.lineTo(corners[i].x, corners[i].y)); ctx.closePath(); ctx.fill(); });
    }
    ctx.strokeStyle = stroke; ctx.lineWidth = width; ctx.beginPath();
    edges.forEach(([a,b]) => { ctx.moveTo(corners[a].x,corners[a].y); ctx.lineTo(corners[b].x,corners[b].y); });
    ctx.stroke();
  }

  function drawMeshBounds(rect) { const box = meshDomainBox(); if (box) drawBox(rect, box, "rgba(51,56,61,.7)", "rgba(95,100,105,.06)", 1.2); }
  function drawDenseRegion(rect) { if (state.mesh && state.mesh.dense_box) drawBox(rect, state.mesh.dense_box, "rgba(26,120,111,.8)", "rgba(42,132,122,.10)", 1.2); }

  function amrBlockBox(block) {
    return { x0: Math.min(block.start[0], block.end[0]), x1: Math.max(block.start[0], block.end[0]), y0: Math.min(block.start[1], block.end[1]), y1: Math.max(block.start[1], block.end[1]), z0: Math.min(block.start[2], block.end[2]), z1: Math.max(block.start[2], block.end[2]) };
  }

  function rgba(hex, alpha) {
    const value = hex.replace("#", "");
    return `rgba(${parseInt(value.slice(0,2),16)},${parseInt(value.slice(2,4),16)},${parseInt(value.slice(4,6),16)},${alpha})`;
  }

  function drawAmrRegions(rect) {
    state.staticAmrBlocks.forEach(block => { const color = AMR_COLORS[(Number(block.layer) - 1) % AMR_COLORS.length]; drawBox(rect, amrBlockBox(block), rgba(color,.7), rgba(color,.07), 1.2); });
    state.cases.forEach(item => {
      if (!item.visible) return;
      (item.amr_blocks || []).forEach(block => { const color = AMR_COLORS[(Number(block.layer) - 1) % AMR_COLORS.length]; drawBox(rect, amrBlockBox(block), rgba(color,item.opacity), rgba(color,item.opacity * .10), 1.3); });
    });
  }

  function sample(values, limit) {
    if (values.length <= limit) return values;
    const result = [];
    for (let i = 0; i < limit; i += 1) result.push(values[Math.round(i * (values.length - 1) / (limit - 1))]);
    return result;
  }

  function drawLine(rect, a, b) { const p = project(rect, a), q = project(rect, b); ctx.moveTo(p.x,p.y); ctx.lineTo(q.x,q.y); }
  function drawSampledGrid(rect) {
    if (!state.mesh || !state.mesh.x || !state.mesh.y) return;
    const x = state.mesh.x, y = state.mesh.y, z = state.mesh.z && state.mesh.z.length ? state.mesh.z : [0];
    const xs = sample(x, MAX_GRID_LINES), ys = sample(y, MAX_GRID_LINES), zs = sample(z, Math.min(28, MAX_GRID_LINES));
    ctx.strokeStyle = "rgba(47,127,193,.20)"; ctx.lineWidth = .5; ctx.beginPath();
    ys.forEach(yy => zs.forEach(zz => drawLine(rect, [x[0],yy,zz], [x[x.length-1],yy,zz])));
    xs.forEach(xx => zs.forEach(zz => drawLine(rect, [xx,y[0],zz], [xx,y[y.length-1],zz])));
    if (state.mesh.z && state.mesh.z.length) xs.forEach(xx => ys.forEach(yy => drawLine(rect, [xx,yy,z[0]], [xx,yy,z[z.length-1]])));
    ctx.stroke();
  }

  function project(rect, point) {
    return window.PicarViewportCore.projectPoint(rect, state.bounds, { mode: state.viewMode, angleX: state.angleX, angleY: state.angleY, zoom: state.zoom, panX: state.panX, panY: state.panY }, point[0], point[1], point[2]);
  }

  function setView(mode) {
    state.viewMode = mode;
    if (mode === "iso") { state.angleX = 0.62; state.angleY = -0.78; }
    if (mode === "top") { state.angleX = 1.55; state.angleY = 0; }
    ["top", "iso", "xy", "xz", "yz"].forEach(id => el[id].classList.toggle("active", id === mode));
    fit();
  }

  function fit() { state.zoom = 1; state.panX = 0; state.panY = 0; requestDraw(); }
  function resetView() { setView("iso"); }
  function setStatus(text) { el.status.textContent = text; }
  function escapeHtml(text) { return String(text).replace(/[&<>"']/g, ch => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" })[ch]); }

  el.canvas.addEventListener("mousedown", event => {
    event.preventDefault(); state.dragging = true;
    state.dragMode = event.ctrlKey || window.PicarViewportCore.isPlaneView(state.viewMode) ? "pan" : "rotate";
    state.lastX = event.clientX; state.lastY = event.clientY;
  });
  window.addEventListener("mousemove", event => {
    if (!state.dragging) return;
    const dx = event.clientX - state.lastX, dy = event.clientY - state.lastY;
    if (state.dragMode === "pan" || event.ctrlKey || window.PicarViewportCore.isPlaneView(state.viewMode)) { state.panX += dx; state.panY += dy; }
    else { state.angleY += dx * 0.008; state.angleX = Math.max(-1.55, Math.min(1.55, state.angleX + dy * 0.008)); }
    state.lastX = event.clientX; state.lastY = event.clientY; requestDraw();
  });
  window.addEventListener("mouseup", () => { state.dragging = false; state.dragMode = null; requestDraw(); });
  el.canvas.addEventListener("wheel", event => { event.preventDefault(); state.zoom = Math.max(0.05, Math.min(80, state.zoom * (event.deltaY < 0 ? 1.12 : 0.89))); state.interactingUntil = performance.now() + 180; requestDraw(); }, { passive: false });
  window.addEventListener("resize", requestDraw);
  el.loadBodies.addEventListener("click", loadBodies); el.addGroup.addEventListener("click", () => addGroup());
  el.preview.addEventListener("click", preview); el.create.addEventListener("click", createCases); el.fit.addEventListener("click", fit); el.reset.addEventListener("click", resetView);
  ["top", "iso", "xy", "xz", "yz"].forEach(id => el[id].addEventListener("click", () => setView(id)));
  [el.showMeshBounds, el.showDenseRegion, el.showFullMesh, el.showAmrRegions].forEach(node => node.addEventListener("change", () => { recomputeBounds(); fit(); }));
  loadBodies();
})();
