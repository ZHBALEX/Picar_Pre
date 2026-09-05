(function () {
  const MAX_POINTS = 35000;
  const INTERACTIVE_POINTS = 8000;
  const el = Object.fromEntries(["source", "output", "casePrefix", "fortStart", "componentOrder", "loadBodies", "addGroup", "groups", "preview", "create", "cases", "status", "canvas", "reset", "top", "iso", "xy", "xz", "yz", "fit"].map(id => [id, document.getElementById(id)]));
  const ctx = el.canvas.getContext("2d");
  const state = {
    staticBodies: [], cases: [], bounds: null,
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
    if (health.api_version !== "motion-center-v6") {
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
      setStatus(`${result.bodies.length} bodies available (1-${result.bodies.length})\n` + result.bodies.map(body => `Body ${body.body_id}: ${body.node_count.toLocaleString()} nodes · ${body.has_fort ? body.fort : "no fort"}`).join("\n"));
    } catch (error) {
      setStatus(error.message || String(error));
    }
  }

  function addGroup(bodyIds = "", x = "0", y = "0", z = "0", rx = "0", ry = "0", rz = "0") {
    const card = document.createElement("div");
    card.className = "group-card";
    card.innerHTML = `<div class="group-head"><label>Body IDs<input data-field="body_ids" value="${escapeHtml(bodyIds)}" placeholder="2-4"></label><button type="button">Remove</button></div><div class="axis-grid"><label>X offsets<input data-field="x" value="${escapeHtml(x)}"></label><label>Y offsets<input data-field="y" value="${escapeHtml(y)}"></label><label>Z offsets<input data-field="z" value="${escapeHtml(z)}"></label></div><div class="axis-grid rotation-grid"><label>RX degrees<input data-field="rx" value="${escapeHtml(rx)}"></label><label>RY degrees<input data-field="ry" value="${escapeHtml(ry)}"></label><label>RZ degrees<input data-field="rz" value="${escapeHtml(rz)}"></label></div>`;
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
      setStatus(`${state.cases.length} cases · ${sent.toLocaleString()} sampled points\n${pivots.join("\n")}\nStatic bodies are drawn once. Preview wrote no files.`);
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
    state.staticBodies.forEach(include);
    state.cases.forEach(item => item.bodies.forEach(include));
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
  loadBodies();
})();
