const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');
const Module = require('node:module');
const test = require('node:test');
const assert = require('node:assert/strict');

const root = path.resolve(__dirname, '..');
const composites = [];
const dims = {};
function fakeSharp(input) {
  const chain = {
    metadata: async () => { const d = dims[input] || { width: 10, height: 10 }; return { width: d.width, height: d.height, format: 'png', channels: 4, size: 1, hasAlpha: true }; },
    resize: () => chain, ensureAlpha: () => chain, normalize: () => chain,
    composite: (layers) => { composites.push({ input, layers }); return chain; },
    toBuffer: async () => Buffer.from([0]),
    toFile: async (out) => { fs.mkdirSync(path.dirname(out), { recursive: true }); fs.writeFileSync(out, 'x'); return {}; },
  };
  return chain;
}
fakeSharp.default = fakeSharp;
const origLoad = Module._load;
Module._load = function (request, parent, isMain) {
  if (request === 'sharp') return fakeSharp;
  return origLoad.call(this, request, parent, isMain);
};
require('ts-node').register({ transpileOnly: true, compilerOptions: { module: 'commonjs' } });
const { ImageProcessor } = require(path.join(root, 'src/services/ImageProcessor.ts'));

test('bottom-right watermark sits exactly the configured margin from the edge', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'wm-'));
  const input = path.join(dir, 'in.png');
  const mark = path.join(dir, 'mark.png');
  fs.writeFileSync(input, 'x');
  fs.writeFileSync(mark, 'x');
  dims[input] = { width: 1000, height: 1000 };
  dims[mark] = { width: 100, height: 50 };
  const proc = new ImageProcessor();
  await proc.watermark({ input, watermark: mark, output: path.join(dir, 'out.png'), opacity: 0.2, scale: 0.2, margin: 20, position: 'bottom-right' });
  const final = composites.find((c) => c.input === input);
  assert.ok(final, 'final composite onto input image was not called');
  assert.equal(final.layers[0].left, 780);
  assert.equal(final.layers[0].top, 880);
});
