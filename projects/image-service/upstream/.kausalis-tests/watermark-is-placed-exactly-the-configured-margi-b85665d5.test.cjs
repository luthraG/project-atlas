require('ts-node').register({ transpileOnly: true, compilerOptions: { module: 'commonjs', esModuleInterop: true } });
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');
const fs = require('fs');
const os = require('os');
const Module = require('module');

const composites = [];
function makeChain(src) {
  const chain = {
    metadata: async () => (String(src).includes('logo') ? { width: 100, height: 100, format: 'png' } : { width: 1000, height: 800, format: 'png', channels: 3, space: 'srgb', hasAlpha: false }),
    resize() { return chain; },
    ensureAlpha() { return chain; },
    normalize() { return chain; },
    composite(arr) { composites.push(arr); return chain; },
    toBuffer: async () => Buffer.from([1, 2, 3]),
    toFile: async (p) => { fs.writeFileSync(p, Buffer.from([0])); return { width: 1000, height: 800, size: 1 }; },
  };
  return new Proxy(chain, { get(t, k) { if (k in t) return t[k]; if (k === 'then') return undefined; return () => t; } });
}
function fakeSharp(src) { return makeChain(src); }
fakeSharp.default = fakeSharp;
const origLoad = Module._load;
Module._load = function (request, parent, isMain) {
  if (request === 'sharp') return fakeSharp;
  return origLoad.apply(this, arguments);
};

const root = path.resolve(__dirname, '..');
const { ImageProcessor } = require(path.join(root, 'src/services/ImageProcessor.ts'));

test('watermark is placed exactly the configured margin from the bottom-right edge', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'wm-'));
  const input = path.join(dir, 'photo.png');
  const logo = path.join(dir, 'logo.png');
  fs.writeFileSync(input, Buffer.from([0]));
  fs.writeFileSync(logo, Buffer.from([0]));
  const output = path.join(dir, 'out.png');
  await ImageProcessor.getInstance().watermark({ input, watermark: logo, output, scale: 0.2, margin: 20, position: 'bottom-right', opacity: 0.2 });
  const placed = composites.map((a) => a[0]).find((c) => c && c.blend === 'over');
  assert.ok(placed, 'final composite was not called');
  assert.equal(placed.left, 780);
  assert.equal(placed.top, 580);
});
