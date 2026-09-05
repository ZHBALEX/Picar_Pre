(function (root) {
  function dot3(a, b) {
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  }

  function cross3(a, b) {
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  }

  function normalize3(v) {
    const length = Math.hypot(v[0], v[1], v[2]) || 1;
    return [v[0] / length, v[1] / length, v[2] / length];
  }

  function cameraBasis(view) {
    const elevation = view.angleX;
    const azimuth = view.angleY;
    const cosElev = Math.cos(elevation);
    if (Math.abs(cosElev) < 0.03) {
      const topSign = elevation >= 0 ? 1 : -1;
      return { right: [1, 0, 0], up: [0, topSign, 0], forward: [0, 0, -topSign] };
    }
    const camera = normalize3([cosElev * Math.cos(azimuth), cosElev * Math.sin(azimuth), Math.sin(elevation)]);
    const forward = [-camera[0], -camera[1], -camera[2]];
    const right = normalize3(cross3(forward, [0, 0, 1]));
    return { right, up: normalize3(cross3(right, forward)), forward };
  }

  function planeAxes(mode) {
    if (mode === "xz") return { u: 0, v: 2, d: 1 };
    if (mode === "yz") return { u: 1, v: 2, d: 0 };
    return { u: 0, v: 1, d: 2 };
  }

  function isPlaneView(mode) {
    return mode === "xy" || mode === "xz" || mode === "yz";
  }

  function projectPoint(rect, bounds, view, x, y, z) {
    if (isPlaneView(view.mode)) {
      const axes = planeAxes(view.mode);
      const values = [x, y, z];
      const du = Math.max(bounds.max[axes.u] - bounds.min[axes.u], 1e-12);
      const dv = Math.max(bounds.max[axes.v] - bounds.min[axes.v], 1e-12);
      const scale = 0.84 * Math.min(rect.width / du, rect.height / dv) * view.zoom;
      return {
        x: rect.width / 2 + view.panX + (values[axes.u] - 0.5 * (bounds.min[axes.u] + bounds.max[axes.u])) * scale,
        y: rect.height / 2 + view.panY - (values[axes.v] - 0.5 * (bounds.min[axes.v] + bounds.max[axes.v])) * scale,
        depth: values[axes.d],
      };
    }
    const centered = [x - 0.5 * (bounds.min[0] + bounds.max[0]), y - 0.5 * (bounds.min[1] + bounds.max[1]), z - 0.5 * (bounds.min[2] + bounds.max[2])];
    const basis = cameraBasis(view);
    const scale = 0.78 * Math.min(rect.width, rect.height) / Math.max(bounds.span, 1e-12) * view.zoom;
    return {
      x: rect.width / 2 + view.panX + dot3(centered, basis.right) * scale,
      y: rect.height / 2 + view.panY - dot3(centered, basis.up) * scale,
      depth: dot3(centered, basis.forward),
    };
  }

  root.PicarViewportCore = { cameraBasis, isPlaneView, planeAxes, projectPoint };
})(window);
