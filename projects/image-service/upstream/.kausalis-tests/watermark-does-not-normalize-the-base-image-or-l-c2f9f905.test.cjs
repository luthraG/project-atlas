require('ts-node').register({ transpileOnly: true, compilerOptions: { module: 'commonjs', esModuleInterop: true } });
const test = require('node:test');
const assert = require('node:assert/strict');
const Module = require('node:module');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const calls = [];
function fakeSharp(input) {
  const inst = {
    metadata: async () => (typeof input === 'string' && input.includes('wm') ? { width: 200, height: 100, format: 'png' } : { width: 1000, height: 800, format: 'png' }),
    resize() { calls.push('resize'); return inst; },
    ensureAlpha() { return inst; },
    composite() { calls.push('composite'); return inst; },
    normalize() { calls.push('normalize'); return inst; },
    normalise() { calls.push('normalize'); return inst; },
    toBuffer: async () => Buffer.alloc(4),
    toFile: async (p) => { fs.writeFileSync(p, Buffer.alloc(4)); return { width: 1000, height: 800, format: 'png', size: 4 }; },
  };
  return inst;
}
fakeSharp.default = fakeSharp;
const origLoad = Module._load;
Module._load = function (request, parent, isMain) {
  if (request === 'sharp') return fakeSharp;
  return origLoad.apply(this, arguments);
};

const root = path.resolve(__dirname, '..');

test('watermark does not normalize the base image or log a luminance failure', async () => {
  const { logger } = require(path.join(root, 'src/utils/logger.ts'));
  const errors = [];
  const origError = logger.error;
  logger.error = (msg) => { errors.push(String(msg)); };
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'wm-'));
  const input = path.join(tmp, 'base.png');
  const wm = path.join(tmp, 'wm.png');
  fs.writeFileSync(input, Buffer.alloc(4));
  fs.writeFileSync(wm, Buffer.alloc(4));
  try {
    const { ImageProcessor } = require(path.join(root, 'src/services/ImageProcessor.ts'));
    await ImageProcessor.getInstance().watermark({ input, watermark: wm, output: path.join(tmp, 'out.png'), opacity: 0.2, scale: 0.2, margin: 20 });
  } finally {
    logger.error = origError;
  }
  assert.ok(!calls.includes('normalize'), 'base image must not be normalized');
  assert.ok(!errors.some((m) => m.includes('luminance profile was not preserved')), 'no unconditional luminance failure log');
});
