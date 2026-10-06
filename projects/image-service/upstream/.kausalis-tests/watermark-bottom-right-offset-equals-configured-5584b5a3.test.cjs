process.env.TS_NODE_TRANSPILE_ONLY = 'true';
require('ts-node/register');
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');
const fs = require('fs');
const os = require('os');
const Module = require('module');

const root = path.resolve(__dirname, '..');
const composites = [];
function fakeSharp(input) {
  const src = String(input);
  const api = {
    metadata: async () => (src.includes('logo') ? { width: 100, height: 50, format: 'png' } : { width: 1000, height: 800, format: 'png' }),
    resize() { return api; },
    ensureAlpha() { return api; },
    normalize() { return api; },
    composite(arr) { composites.push(arr); return api; },
    toBuffer: async () => Buffer.from([0]),
    toFile: async (p) => { fs.writeFileSync(p, 'x'); return {}; },
  };
  return api;
}
const sharpModule = Object.assign(fakeSharp, { __esModule: true, default: fakeSharp });
const origLoad = Module._load;
Module._load = function (request, parent, isMain) {
  if (request === 'sharp') return sharpModule;
  return origLoad.apply(this, arguments);
};

test('watermark bottom-right offset equals configured margin', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'wm-'));
  const input = path.join(dir, 'input.png');
  const logo = path.join(dir, 'logo.png');
  fs.writeFileSync(input, 'x');
  fs.writeFileSync(logo, 'x');
  const { ImageProcessor } = require(path.join(root, 'src/services/ImageProcessor.ts'));
  await ImageProcessor.getInstance().watermark({ input, watermark: logo, scale: 0.2, margin: 20, position: 'bottom-right', opacity: 0.5, output: path.join(dir, 'out.png') });
  const placed = composites.map((a) => a[0]).filter((c) => c && typeof c.left === 'number');
  assert.ok(placed.length > 0, 'final composite was not reached');
  const last = placed[placed.length - 1];
  assert.equal(last.left, 780);
  assert.equal(last.top, 680);
});
