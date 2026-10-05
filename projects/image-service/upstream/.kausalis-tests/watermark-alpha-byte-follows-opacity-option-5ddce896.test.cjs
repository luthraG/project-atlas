require('ts-node').register({ transpileOnly: true, compilerOptions: { module: 'commonjs', esModuleInterop: true } });
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');
const Module = require('node:module');

const composites = [];
function fakeSharp() {
  const chain = {
    metadata: async () => ({ width: 1000, height: 800, format: 'png', hasAlpha: true }),
    resize() { return chain; },
    extract() { return chain; },
    ensureAlpha() { return chain; },
    normalize() { return chain; },
    composite(arr) { composites.push(arr); return chain; },
    toBuffer: async () => Buffer.from([0]),
    toFile: async (p) => { fs.writeFileSync(p, 'x'); return {}; },
  };
  return chain;
}
fakeSharp.default = fakeSharp;
const origLoad = Module._load;
Module._load = function (request, parent, isMain) {
  if (request === 'sharp') return fakeSharp;
  return origLoad.apply(this, arguments);
};

const root = path.resolve(__dirname, '..');
const { ImageProcessor } = require(path.join(root, 'src/services/ImageProcessor.ts'));

test('watermark alpha byte follows opacity option', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'wm-'));
  const input = path.join(dir, 'in.png');
  const mark = path.join(dir, 'mark.png');
  fs.writeFileSync(input, 'x');
  fs.writeFileSync(mark, 'x');
  const output = path.join(dir, 'out.png');
  await ImageProcessor.getInstance().watermark({ input, watermark: mark, output, opacity: 0.5, scale: 0.2 });
  const tile = composites.flat().find((c) => c && c.raw && c.tile);
  assert.ok(tile, 'alpha tile composite was not reached');
  assert.equal(tile.input[3], 128);
});
