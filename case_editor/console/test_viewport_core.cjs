const assert = require('node:assert/strict');
global.window = {};
require('./viewport_core.js');
const { cameraBasis, projectPoint } = window.PicarViewportCore;
const dot = (a, b) => a.reduce((sum, v, i) => sum + v * b[i], 0);
const cross = (a, b) => [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]];
const close = (a, b) => assert.ok(Math.abs(a-b) < 1e-10, `${a} != ${b}`);
for (const upAxis of ['y', 'z']) {
  for (const angleX of [-Math.PI/2, -1.55, 0, 0.62, 1.54, 1.55, Math.PI/2]) {
    for (const angleY of [-2, -0.78, 0, 2]) {
      const { right, up, forward } = cameraBasis({ upAxis, angleX, angleY });
      for (const v of [right, up, forward]) close(dot(v, v), 1);
      close(dot(right, up), 0);
      // Screen right x screen up points toward the viewer, opposite forward.
      close(dot(cross(right, up), forward), -1);
    }
  }
  const before = cameraBasis({upAxis, angleX: 1.54, angleY: -0.78});
  const after = cameraBasis({upAxis, angleX: 1.55, angleY: -0.78});
  assert.ok(dot(before.right, after.right) > 0.9999);
  assert.ok(dot(before.up, after.up) > 0.9999);
  const top = cameraBasis({upAxis, angleX: Math.PI/2, angleY: -Math.PI/2});
  close(top.right[0], 1);
  close(top.forward[upAxis === 'y' ? 1 : 2], -1);
  const view = {upAxis, mode: 'iso', angleX: 0.62, angleY: -0.78, zoom: 1, panX: 0, panY: 0};
  const rect = {width: 800, height: 600};
  const bounds = {min: [-1,-1,-1], max: [1,1,1], span: 2};
  const vertical = upAxis === 'y' ? [0,1,0] : [0,0,1];
  const p = projectPoint(rect, bounds, view, ...vertical);
  close(p.x, 400);
  assert.ok(p.y < 300);
}
console.log('Viewport handedness, pole continuity, and Y/Z height checks passed.');
