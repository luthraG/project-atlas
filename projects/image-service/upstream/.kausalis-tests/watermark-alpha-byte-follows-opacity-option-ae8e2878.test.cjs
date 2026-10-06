const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');
const Module = require('node:module');

const root = path.resolve(__dirname, '..');
require(require.resolve('ts-node', { paths: [root] })).register({ transpileOnly: true, compilerOptions: { module: 'commonjs' } });

const compositeCalls = [];
function fakeSharp(input) {
  const chain = {
    metadata: async () => (String(input).includes('wm') ? { width: 200, height: 100, format: 'png' } : { width: 1000, height: 800, format: 'png' }),
    resize() { return chain; },
    ensureAlpha() { return chain; },
    normalize() { return chain; },
    extract() { return chain; },
    composite(arr) { compositeCalls.push(arr); return chain; },
    toBuffer: async () => Buffer.alloc(4),
    toFile: async (out) => { fs.writeFileSync(out, ''); return {}; },
  };
  return chain;
}
fakeSharp.default = fakeSharp;
const origLoad = Module._load;
Module._load = function (request, parent, isMain) {
  if (request === 'sharp') return fakeSharp;
  return origLoad.apply(this, arguments);
};

test('watermark alpha byte follows opacity option', async () => {
  const { logger } = require(path.join(root, 'src/utils/logger'));
  const errors = [];
  logger.error = (msg) => { errors.push(String(msg)); };
  logger.info = () => {};
  const { ImageProcessor } = require(path.join(root, 'src/services/ImageProcessor.ts'));
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'wm-'));
  const input = path.join(dir, 'input.png');
  const wm = path.join(dir, 'wm.png');
  fs.writeFileSync(input, '');
  fs.writeFileSync(wm, '');
  const proc = new ImageProcessor();
  await proc.watermark({ input, watermark: wm, output: path.join(dir, 'out.png'), opacity: 0.5, scale: 0.2 });
  const tile = compositeCalls.flat().find((c) => c && c.raw && c.blend === 'dest-in');
  assert.ok(tile, 'dest-in alpha tile composite was not invoked');
  assert.equal(tile.input[3], 128);
  assert.ok(!errors.some((e) => e.includes('Opacity verification failed')), errors.join('\n'));
});
