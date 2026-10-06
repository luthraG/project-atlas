const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');
const fs = require('fs');
const os = require('os');
const Module = require('module');

const captured = [];
function fakeSharp() {
  const chain = {
    metadata: async () => ({ width: 1000, height: 500, format: 'png', hasAlpha: true, channels: 4 }),
    resize() { return chain; },
    ensureAlpha() { return chain; },
    normalize() { return chain; },
    extract() { return chain; },
    composite(layers) { for (const l of layers) { if (l && l.raw) captured.push(Buffer.from(l.input)); } return chain; },
    toBuffer: async () => Buffer.alloc(4),
    toFile: async (p) => { fs.mkdirSync(path.dirname(p), { recursive: true }); fs.writeFileSync(p, Buffer.alloc(8)); return {}; },
  };
  return chain;
}
fakeSharp.default = fakeSharp;
fakeSharp.__esModule = true;
const origLoad = Module._load;
Module._load = function (request, parent, isMain) {
  if (request === 'sharp') return fakeSharp;
  return origLoad.apply(this, arguments);
};

require('ts-node').register({ transpileOnly: true, compilerOptions: { module: 'commonjs', esModuleInterop: true } });
const root = path.resolve(__dirname, '..');
const { ImageProcessor } = require(path.join(root, 'src/services/ImageProcessor.ts'));

test('watermark alpha byte follows opacity not scale', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'wm-'));
  const input = path.join(dir, 'in.png');
  const wm = path.join(dir, 'wm.png');
  fs.writeFileSync(input, Buffer.alloc(8));
  fs.writeFileSync(wm, Buffer.alloc(8));
  const output = path.join(dir, 'out.png');
  await ImageProcessor.getInstance().watermark({ input, watermark: wm, output, opacity: 0.5, scale: 0.2 });
  assert.ok(captured.length >= 1, 'alpha mask composite was not reached');
  assert.equal(captured[0][3], 128);
});
