require('ts-node').register({ transpileOnly: true });
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');
const fs = require('fs');
const os = require('os');
const Module = require('module');

const captured = [];
function fakeSharp() {
  const api = {
    metadata: async () => ({ width: 1000, height: 800, format: 'png', hasAlpha: true, channels: 4 }),
    resize: () => api,
    extract: () => api,
    ensureAlpha: () => api,
    normalize: () => api,
    composite: (layers) => { captured.push(...layers); return api; },
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

test('watermark alpha byte follows opacity not scale', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'wm-'));
  const input = path.join(dir, 'in.png');
  const mark = path.join(dir, 'mark.png');
  fs.writeFileSync(input, 'x');
  fs.writeFileSync(mark, 'x');
  await ImageProcessor.getInstance().watermark({ input, watermark: mark, output: path.join(dir, 'out.png'), opacity: 0.5, scale: 0.2 });
  const mask = captured.find((l) => l && l.blend === 'dest-in');
  assert.ok(mask, 'dest-in alpha mask layer was composited');
  assert.equal(mask.input[3], 128);
});
