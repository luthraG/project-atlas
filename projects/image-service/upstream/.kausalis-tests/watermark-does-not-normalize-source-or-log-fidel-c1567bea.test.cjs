process.env.TS_NODE_TRANSPILE_ONLY = 'true';
require('ts-node/register');
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');
const Module = require('node:module');

const calls = [];
function fakeSharp(input) {
  const target = {};
  const proxy = new Proxy(target, {
    get(_t, prop) {
      if (prop === 'then') return undefined;
      if (prop === 'metadata') return async () => ({ width: 100, height: 100, format: 'png', channels: 4, size: 0 });
      if (prop === 'toBuffer') return async () => Buffer.alloc(4);
      if (prop === 'toFile') return async (p) => { fs.writeFileSync(p, ''); return { width: 100, height: 100, size: 0 }; };
      if (prop === 'stats') return async () => ({});
      return (...args) => { calls.push({ input, method: String(prop) }); return proxy; };
    },
  });
  return proxy;
}
fakeSharp.default = fakeSharp;
const origLoad = Module._load;
Module._load = function (request, parent, isMain) {
  if (request === 'sharp') return fakeSharp;
  return origLoad.apply(this, arguments);
};

const root = path.resolve(__dirname, '..');
const { imageProcessor } = require(path.join(root, 'src/services/ImageProcessor.ts'));
const { logger } = require(path.join(root, 'src/utils/logger.ts'));

test('watermark does not normalize source or log fidelity failure', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'wm-'));
  const input = path.join(dir, 'input.jpg');
  const logo = path.join(dir, 'logo.png');
  fs.writeFileSync(input, 'x');
  fs.writeFileSync(logo, 'x');
  const errors = [];
  const origError = logger.error;
  logger.error = (msg) => { errors.push(String(msg)); };
  let result;
  try {
    result = await imageProcessor.watermark({ input, watermark: logo, output: path.join(dir, 'out.jpg'), opacity: 0.2 });
  } finally {
    logger.error = origError;
  }
  assert.equal(result.success, true, String(result.error));
  const normalized = calls.filter((c) => c.input === input && c.method === 'normalize');
  assert.equal(normalized.length, 0, 'source image was normalized');
  assert.equal(errors.some((e) => e.includes('Output fidelity check failed')), false);
});
