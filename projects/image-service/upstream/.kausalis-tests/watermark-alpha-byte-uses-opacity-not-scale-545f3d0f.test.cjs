require('ts-node').register({ transpileOnly: true, compilerOptions: { module: 'commonjs', esModuleInterop: true } });
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');
const Module = require('node:module');

const composites = [];
function fakeSharp(input) {
  const api = {
    metadata: async () => ({ width: 1000, height: 800, format: 'png', channels: 4, hasAlpha: true }),
    resize() { return api; },
    extract() { return api; },
    ensureAlpha() { return api; },
    normalize() { return api; },
    composite(layers) { composites.push(layers); return api; },
    toBuffer: async () => Buffer.from([0, 0, 0, 0]),
    toFile: async (p) => { fs.writeFileSync(p, 'x'); return {}; },
  };
  return api;
}
fakeSharp.default = fakeSharp;
const origLoad = Module._load;
Module._load = function (request, parent, isMain) {
  if (request === 'sharp') return fakeSharp;
  return origLoad.apply(this, arguments);
};

const root = path.resolve(__dirname, '..');
const { ImageProcessor } = require(path.join(root, 'src/services/ImageProcessor.ts'));

test('watermark alpha byte uses opacity not scale', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'wm-'));
  const input = path.join(dir, 'input.png');
  const wm = path.join(dir, 'wm.png');
  fs.writeFileSync(input, 'x');
  fs.writeFileSync(wm, 'x');
  const output = path.join(dir, 'out.png');
  await ImageProcessor.getInstance().watermark({ input, watermark: wm, output, opacity: 0.5, scale: 0.2 });
  const raw = composites.flat().find((l) => l && l.raw && Buffer.isBuffer(l.input) && l.input.length === 4);
  assert.ok(raw, 'expected alpha tile composite to be built');
  assert.equal(raw.input[3], 128);
});
