(function () {
  const axes = ["x", "y", "z"];
  const ids = [
    "scaleRef", "relax", "method", "priority", "maxChange", "searchWindow",
    "optimizeCounts", "confirmInput", "downloadInput", "copyInput",
    "stats", "qualityTable", "inputPreview", "gridCanvas", "statusText",
  ];
  axes.forEach((axis) => {
    [
      "Start", "DenseStart", "DenseEnd", "End", "LeftStretch", "LeftUniform",
      "DenseCount", "RightUniform", "RightStretch", "LeftLayerLength",
      "RightLayerLength", "IdealDelta", "LeftRatio", "RightRatio",
    ].forEach((suffix) => ids.push(axis + suffix));
  });

  const el = Object.fromEntries(ids.map((id) => [id, document.getElementById(id)]));
  let confirmedText = "";

  init();

  function init() {
    Object.entries(el).forEach(([id, node]) => {
      if (!node || id === "gridCanvas" || id === "qualityTable" || id === "inputPreview" || id === "stats" || id === "statusText") {
        return;
      }
      node.addEventListener("input", markDirtyAndUpdate);
      node.addEventListener("change", markDirtyAndUpdate);
    });
    el.optimizeCounts.addEventListener("click", optimizeCounts);
    el.confirmInput.addEventListener("click", confirmInput);
    el.downloadInput.addEventListener("click", downloadInput);
    el.copyInput.addEventListener("click", copyInput);
    window.addEventListener("resize", update);
    update();
  }

  function markDirtyAndUpdate() {
    el.statusText.textContent = "Not confirmed";
    update();
  }

  function readDesign() {
    return {
      scaleRef: num("scaleRef"),
      relax: num("relax"),
      method: el.method.value,
      priority: el.priority.value,
      maxChange: num("maxChange"),
      searchWindow: Math.max(1, int("searchWindow")),
      axes: Object.fromEntries(axes.map((axis) => [axis, readAxis(axis)])),
    };
  }

  function readAxis(axis) {
    return {
      axis,
      start: num(axis + "Start"),
      denseStart: num(axis + "DenseStart"),
      denseEnd: num(axis + "DenseEnd"),
      end: num(axis + "End"),
      leftStretch: Math.max(0, int(axis + "LeftStretch")),
      leftUniform: Math.max(0, int(axis + "LeftUniform")),
      denseCount: Math.max(1, int(axis + "DenseCount")),
      rightUniform: Math.max(0, int(axis + "RightUniform")),
      rightStretch: Math.max(0, int(axis + "RightStretch")),
      leftLayerLength: Math.max(0, num(axis + "LeftLayerLength")),
      rightLayerLength: Math.max(0, num(axis + "RightLayerLength")),
      idealDelta: Math.max(1e-12, num(axis + "IdealDelta")),
      leftRatio: Math.max(1e-12, num(axis + "LeftRatio")),
      rightRatio: Math.max(1e-12, num(axis + "RightRatio")),
    };
  }

  function update() {
    const design = readDesign();
    const params = buildParams(design);
    const validation = validateDesign(design);
    const qualities = axes.map((axis) => axisQuality(design.axes[axis]));
    const inputText = formatInput(params);
    el.inputPreview.textContent = inputText;
    el.stats.textContent = validation.length ? validation[0] : summaryText(design, qualities);
    renderQualityTable(qualities);
    renderCanvas(design);
  }

  function optimizeCounts() {
    const design = readDesign();
    axes.forEach((axis) => {
      const cfg = design.axes[axis];
      const optimized = optimizeAxis(cfg, design);
      el[axis + "DenseCount"].value = optimized.count;
      const center = 0.5 * (cfg.denseStart + cfg.denseEnd);
      const denseLength = optimized.denseLength;
      el[axis + "DenseStart"].value = formatNumber(center - denseLength / 2);
      el[axis + "DenseEnd"].value = formatNumber(center + denseLength / 2);
    });
    el.statusText.textContent = "Optimized, not confirmed";
    update();
  }

  function confirmInput() {
    confirmedText = el.inputPreview.textContent;
    el.statusText.textContent = "Confirmed";
  }

  function downloadInput() {
    const text = confirmedText || el.inputPreview.textContent;
    const blob = new Blob([text + "\n"], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "input.dat";
    link.click();
    URL.revokeObjectURL(url);
  }

  async function copyInput() {
    const text = confirmedText || el.inputPreview.textContent;
    await navigator.clipboard.writeText(text);
    el.statusText.textContent = confirmedText ? "Confirmed text copied" : "Current text copied";
  }

  function buildParams(design) {
    const x = design.axes.x;
    const y = design.axes.y;
    const z = design.axes.z;
    return {
      scale_ref: design.scaleRef,
      Lx: x.end - x.start,
      Ly: y.end - y.start,
      Lz: z.end - z.start,
      x_center_dense: midpointRelative(x),
      y_center_dense: midpointRelative(y),
      z_center_dense: midpointRelative(z),
      Lx_dense: x.denseEnd - x.denseStart,
      Ly_dense: y.denseEnd - y.denseStart,
      Lz_dense: z.denseEnd - z.denseStart,
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
      r_left: x.leftRatio,
      r_right: x.rightRatio,
      r_bottom: y.leftRatio,
      r_top: y.rightRatio,
      r_front: z.leftRatio,
      r_back: z.rightRatio,
      relax: design.relax,
      flag_plot: false,
      flag_preplot: false,
    };
  }

  function optimizeAxis(cfg, design) {
    const denseLength = cfg.denseEnd - cfg.denseStart;
    const sideCount = cfg.leftStretch + cfg.leftUniform + cfg.rightUniform + cfg.rightStretch;
    if (design.method === "table") {
      const target = denseLength / cfg.idealDelta;
      const candidates = preferredCounts(Math.max(64, Math.ceil(target * 2) + 1024));
      const best = candidates
        .map((count) => ({ count, denseLength: count * cfg.idealDelta }))
        .filter((item) => denseChangeAllowed(denseLength, item.denseLength, design.maxChange))
        .filter((item) => geometryValid(cfg, item.denseLength))
        .sort((a, b) => tableScore(a.count, b.count, target, sideCount))[0];
      return best || { count: cfg.denseCount, denseLength };
    }

    const spacing = denseLength / cfg.denseCount;
    const low = Math.max(1, cfg.denseCount - design.searchWindow);
    const high = cfg.denseCount + design.searchWindow;
    const candidates = [];
    for (let count = low; count <= high; count += 1) {
      const nextLength = count * spacing;
      if (denseChangeAllowed(denseLength, nextLength, design.maxChange) && geometryValid(cfg, nextLength)) {
        candidates.push({ count, denseLength: nextLength });
      }
    }
    candidates.sort((a, b) => searchScore(a.count, b.count, cfg.denseCount, sideCount, design.priority));
    return candidates[0] || { count: cfg.denseCount, denseLength };
  }

  function tableScore(a, b, target, sideCount) {
    const aq = countQuality(a);
    const bq = countQuality(b);
    const at = countQuality(a + sideCount);
    const bt = countQuality(b + sideCount);
    return compareTuple(
      [Math.abs(a - target), aq.odd, at.odd, -aq.twos],
      [Math.abs(b - target), bq.odd, bt.odd, -bq.twos],
    );
  }

  function searchScore(a, b, original, sideCount, priority) {
    const aq = countQuality(a);
    const bq = countQuality(b);
    const at = countQuality(a + sideCount);
    const bt = countQuality(b + sideCount);
    if (priority === "balanced") {
      return compareTuple(
        [aq.odd + at.odd, Math.max(aq.odd, at.odd), aq.odd, at.odd, Math.abs(a - original)],
        [bq.odd + bt.odd, Math.max(bq.odd, bt.odd), bq.odd, bt.odd, Math.abs(b - original)],
      );
    }
    return compareTuple(
      [aq.odd, at.odd, Math.max(aq.odd, at.odd), -aq.twos, Math.abs(a - original)],
      [bq.odd, bt.odd, Math.max(bq.odd, bt.odd), -bq.twos, Math.abs(b - original)],
    );
  }

  function axisQuality(cfg) {
    const denseLength = cfg.denseEnd - cfg.denseStart;
    const denseSpacing = denseLength / cfg.denseCount;
    const total = cfg.leftStretch + cfg.leftUniform + cfg.denseCount + cfg.rightUniform + cfg.rightStretch;
    return {
      axis: cfg.axis,
      dense: cfg.denseCount,
      total,
      spacing: denseSpacing,
      denseQuality: countQuality(cfg.denseCount),
      totalQuality: countQuality(total),
    };
  }

  function renderQualityTable(rows) {
    el.qualityTable.innerHTML = `
      <thead>
        <tr>
          <th>Axis</th><th>Dense</th><th>Dense odd</th><th>Dense /2</th>
          <th>Total</th><th>Total odd</th><th>Total /2</th><th>d</th>
        </tr>
      </thead>
      <tbody>
        ${rows.map((row) => `
          <tr>
            <td>${row.axis.toUpperCase()}</td>
            <td>${row.dense}</td>
            <td>${row.denseQuality.odd}</td>
            <td>${row.denseQuality.twos}</td>
            <td>${row.total}</td>
            <td>${row.totalQuality.odd}</td>
            <td>${row.totalQuality.twos}</td>
            <td>${formatNumber(row.spacing)}</td>
          </tr>
        `).join("")}
      </tbody>
    `;
  }

  function renderCanvas(design) {
    const canvas = el.gridCanvas;
    const rect = canvas.parentElement.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.max(1, Math.floor(rect.width * dpr));
    canvas.height = Math.max(1, Math.floor(rect.height * dpr));
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const width = rect.width;
    const height = rect.height;
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = "#eef3f4";
    ctx.fillRect(0, 0, width, height);

    const x = design.axes.x;
    const y = design.axes.y;
    const pad = 34;
    const sx = (width - pad * 2) / Math.max(1e-12, x.end - x.start);
    const sy = (height - pad * 2) / Math.max(1e-12, y.end - y.start);
    const scale = Math.min(sx, sy);
    const ox = pad + (width - pad * 2 - (x.end - x.start) * scale) / 2;
    const oy = pad + (height - pad * 2 - (y.end - y.start) * scale) / 2;
    const mapX = (value) => ox + (value - x.start) * scale;
    const mapY = (value) => oy + (y.end - value) * scale;

    const xs = makeAxisNodes(x);
    const ys = makeAxisNodes(y);
    drawGrid(ctx, xs, ys, mapX, mapY);
    drawRegions(ctx, x, y, mapX, mapY);
  }

  function drawGrid(ctx, xs, ys, mapX, mapY) {
    const xMin = mapX(xs[0]);
    const xMax = mapX(xs[xs.length - 1]);
    const yMin = mapY(ys[0]);
    const yMax = mapY(ys[ys.length - 1]);
    ctx.strokeStyle = "#3d8bd1";
    ctx.lineWidth = 0.55;
    ys.forEach((y) => line(ctx, xMin, mapY(y), xMax, mapY(y)));
    xs.forEach((x) => line(ctx, mapX(x), yMin, mapX(x), yMax));
    ctx.strokeStyle = "#1f2933";
    ctx.lineWidth = 1.2;
    ctx.strokeRect(xMin, yMax, xMax - xMin, yMin - yMax);
  }

  function drawRegions(ctx, x, y, mapX, mapY) {
    const left = mapX(x.denseStart);
    const right = mapX(x.denseEnd);
    const top = mapY(y.denseEnd);
    const bottom = mapY(y.denseStart);
    ctx.fillStyle = "rgba(35, 115, 107, 0.08)";
    ctx.strokeStyle = "#23736b";
    ctx.lineWidth = 2;
    ctx.fillRect(left, top, right - left, bottom - top);
    ctx.strokeRect(left, top, right - left, bottom - top);
  }

  function makeAxisNodes(cfg) {
    const leftTotal = cfg.denseStart - cfg.start;
    const rightTotal = cfg.end - cfg.denseEnd;
    const leftUniformLength = Math.min(cfg.leftLayerLength, Math.max(0, leftTotal));
    const rightUniformLength = Math.min(cfg.rightLayerLength, Math.max(0, rightTotal));
    const leftStretchLength = Math.max(0, leftTotal - leftUniformLength);
    const rightStretchLength = Math.max(0, rightTotal - rightUniformLength);
    const denseSizes = uniformSizes(cfg.denseEnd - cfg.denseStart, cfg.denseCount);
    const leftUniformSizes = uniformSizes(leftUniformLength, cfg.leftUniform);
    const rightUniformSizes = uniformSizes(rightUniformLength, cfg.rightUniform);
    const denseSpacing = denseSizes.length ? denseSizes[0] : 0;
    const leftAdjacent = leftUniformSizes.length ? leftUniformSizes[0] : denseSpacing;
    const rightAdjacent = rightUniformSizes.length ? rightUniformSizes[0] : denseSpacing;
    const sizes = [
      ...smoothStretchSizes(leftStretchLength, cfg.leftStretch, leftAdjacent, "left"),
      ...leftUniformSizes,
      ...denseSizes,
      ...rightUniformSizes,
      ...smoothStretchSizes(rightStretchLength, cfg.rightStretch, rightAdjacent, "right"),
    ];
    const nodes = [cfg.start];
    sizes.forEach((size) => nodes.push(nodes[nodes.length - 1] + size));
    nodes[nodes.length - 1] = cfg.end;
    return nodes;
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

  function formatInput(params) {
    const fields = [
      ["scale_ref", "primary length scale"],
      ["Lx", "domain length in x"],
      ["Ly", "domain length in y"],
      ["Lz", "domain length in z"],
      ["x_center_dense", "dense-region center in x"],
      ["y_center_dense", "dense-region center in y"],
      ["z_center_dense", "dense-region center in z"],
      ["Lx_dense", "dense-region length in x"],
      ["Ly_dense", "dense-region length in y"],
      ["Lz_dense", "dense-region length in z"],
      ["Nx_dense", "dense-region interval count in x"],
      ["Ny_dense", "dense-region interval count in y"],
      ["Nz_dense", "dense-region interval count in z"],
      ["len_left", "left uniform layer length near dense region"],
      ["len_right", "right uniform layer length near dense region"],
      ["len_bottom", "bottom uniform layer length near dense region"],
      ["len_top", "top uniform layer length near dense region"],
      ["len_front", "front uniform layer length near dense region"],
      ["len_back", "back uniform layer length near dense region"],
      ["n_left_stretch", "left stretched interval count"],
      ["n_left_uniform", "left uniform interval count"],
      ["n_right_uniform", "right uniform interval count"],
      ["n_right_stretch", "right stretched interval count"],
      ["n_bottom_stretch", "bottom stretched interval count"],
      ["n_bottom_uniform", "bottom uniform interval count"],
      ["n_top_uniform", "top uniform interval count"],
      ["n_top_stretch", "top stretched interval count"],
      ["n_front_stretch", "front stretched interval count"],
      ["n_front_uniform", "front uniform interval count"],
      ["n_back_uniform", "back uniform interval count"],
      ["n_back_stretch", "back stretched interval count"],
      ["r_left", "left stretching ratio"],
      ["r_right", "right stretching ratio"],
      ["r_bottom", "bottom stretching ratio"],
      ["r_top", "top stretching ratio"],
      ["r_front", "front stretching ratio"],
      ["r_back", "back stretching ratio"],
      ["relax", "relaxation factor"],
      ["flag_plot", "generate plot"],
      ["flag_preplot", "preplot"],
    ];
    return [
      "! Mesh generator parameters",
      ...fields.map(([key, comment]) => `${formatValue(params[key]).padEnd(16, " ")} ! ${comment}`),
    ].join("\n");
  }

  function validateDesign(design) {
    const errors = [];
    axes.forEach((axis) => {
      const cfg = design.axes[axis];
      if (!(cfg.start < cfg.denseStart && cfg.denseStart < cfg.denseEnd && cfg.denseEnd < cfg.end)) {
        errors.push(`${axis.toUpperCase()} ranges must satisfy start < dense start < dense end < end`);
      }
      if (cfg.leftStretch > 0 && cfg.leftLayerLength >= cfg.denseStart - cfg.start) {
        errors.push(`${axis.toUpperCase()} left layer leaves no stretched region`);
      }
      if (cfg.rightStretch > 0 && cfg.rightLayerLength >= cfg.end - cfg.denseEnd) {
        errors.push(`${axis.toUpperCase()} right layer leaves no stretched region`);
      }
    });
    return errors;
  }

  function summaryText(design, rows) {
    const counts = rows.map((row) => `${row.axis.toUpperCase()} ${row.total + 1}`).join(" | ");
    return `grid nodes ${counts}`;
  }

  function preferredCounts(maxCount) {
    const odds = [1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21];
    const values = new Set();
    for (let power = 1; power <= maxCount; power *= 2) {
      odds.forEach((odd) => {
        const value = odd * power;
        if (value > 0 && value <= maxCount) values.add(value);
      });
    }
    return Array.from(values).sort((a, b) => a - b);
  }

  function countQuality(count) {
    let n = Math.max(1, Math.floor(count));
    let twos = 0;
    while (n % 2 === 0) {
      n /= 2;
      twos += 1;
    }
    return { odd: n, twos };
  }

  function geometryValid(cfg, denseLength) {
    const center = 0.5 * (cfg.denseStart + cfg.denseEnd);
    const leftTotal = center - denseLength / 2 - cfg.start;
    const rightTotal = cfg.end - (center + denseLength / 2);
    if (leftTotal <= 0 || rightTotal <= 0) return false;
    if (cfg.leftStretch > 0 && cfg.leftLayerLength >= leftTotal) return false;
    if (cfg.rightStretch > 0 && cfg.rightLayerLength >= rightTotal) return false;
    return true;
  }

  function denseChangeAllowed(oldLength, newLength, maxChange) {
    return Math.abs(newLength - oldLength) <= Math.abs(oldLength) * maxChange + 1e-12;
  }

  function midpointRelative(cfg) {
    return 0.5 * (cfg.denseStart + cfg.denseEnd) - cfg.start;
  }

  function compareTuple(a, b) {
    for (let i = 0; i < a.length; i += 1) {
      if (a[i] < b[i]) return -1;
      if (a[i] > b[i]) return 1;
    }
    return 0;
  }

  function line(ctx, x1, y1, x2, y2) {
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
  }

  function num(id) {
    const value = Number(el[id].value);
    return Number.isFinite(value) ? value : 0;
  }

  function int(id) {
    return Math.floor(num(id));
  }

  function formatNumber(value) {
    return Number(value.toPrecision(10)).toString();
  }

  function formatValue(value) {
    if (typeof value === "boolean") return value ? "T" : "F";
    if (Number.isInteger(value)) return String(value);
    return formatNumber(value);
  }
}());
