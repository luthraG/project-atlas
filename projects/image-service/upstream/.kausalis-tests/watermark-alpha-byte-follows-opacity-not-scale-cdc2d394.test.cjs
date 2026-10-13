require('ts-node').register({ transpileOnly: true, compilerOptions: { module: 'commonjs' } });
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');
const Module = require('node:module');

const composites = [];
function fakeSharp(input) {
  const isWatermark = typeof input === 'string' && path.basename(input) === 'wm.png';
  const chain = {
    metadata: async () => (isWatermark
      ? { width: 200, height: 100, format: 'png', hasAlpha: true }
      : { width: 1000, height: 800, format: 'png', hasAlpha: false }),
    resize() { return chain; },
    extract() { return chain; },
    ensureAlpha() { return chain; },
    normalize() { return chain; },
    rotate() { return chain; },
    toFormat() { return chain; },
    composite(layers) { composites.push(layers); return chain; },
    toBuffer: async () => Buffer.alloc(4),
    toFile: async (out) => { fs.writeFileSync(out, Buffer.alloc(8)); return {}; },
  };
  return chain;
}
const origLoad = Module._load;
Module._load = function (request, parent, isMain) {
  if (request === 'sharp') return fakeSharp;
  return origLoad.apply(this, arguments);
};

const root = path.resolve(__dirname, '..');
const mod = require(path.join(root, 'src/services/ImageProcessor.ts'));
const Cls = mod.ImageProcessor;

test('watermark alpha byte follows opacity not scale', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'wm-'));
  const input = path.join(dir, 'input.png');
  const wm = path.join(dir, 'wm.png');
  fs.writeFileSync(input, Buffer.alloc(8));
  fs.writeFileSync(wm, Buffer.alloc(8));
  const proc = Cls.getInstance();
  composites.length = 0;
  await proc.watermark({ input, watermark: wm, output: path.join(dir, 'out.png'), opacity: 0.5, scale: 0.2 });
  const tile = composites.flat().find((l) => l && l.blend === 'dest-in');
  assert.ok(tile, 'dest-in tile composite not reached');
  // opacity 0.5 -> Math.round(0.5*255) = 128; unfixed line 154 yields Math.round(0.2*255) = 51
  assert.equal(tile.input[3], 128);
});
