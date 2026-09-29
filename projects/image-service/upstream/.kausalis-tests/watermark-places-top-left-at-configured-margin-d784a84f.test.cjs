require('ts-node').register({ transpileOnly: true, compilerOptions: { module: 'commonjs', esModuleInterop: true } });
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');
const fs = require('fs');
const os = require('os');
const Module = require('module');

const root = path.resolve(__dirname, '..');
const composites = [];

function fakeSharp(input) {
  const name = typeof input === 'string' ? path.basename(input) : '';
  const handlers = {
    metadata: async () => name.startsWith('logo')
      ? { width: 100, height: 50, format: 'png', channels: 4, hasAlpha: true, size: 1 }
      : { width: 1000, height: 800, format: 'png', channels: 3, hasAlpha: false, size: 1 },
    composite: (layers) => { composites.push(layers); return proxy; },
    toBuffer: async () => Buffer.from([0]),
    toFile: async (out) => { fs.writeFileSync(out, Buffer.from([0])); return {}; },
  };
  const proxy = new Proxy({}, {
    get(_t, prop) {
      if (prop === 'then') return undefined;
      if (prop in handlers) return handlers[prop];
      return () => proxy;
    },
  });
  return proxy;
}
fakeSharp.default = fakeSharp;

const origLoad = Module._load;
Module._load = function (request) {
  if (request === 'sharp') return fakeSharp;
  return origLoad.apply(this, arguments);
};

const { logger } = require(path.join(root, 'src/utils/logger'));
const { ImageProcessor } = require(path.join(root, 'src/services/ImageProcessor'));

test('watermark places top-left at configured margin', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'wm-'));
  const input = path.join(dir, 'photo.png');
  const logo = path.join(dir, 'logo.png');
  fs.writeFileSync(input, Buffer.from([0]));
  fs.writeFileSync(logo, Buffer.from([0]));
  const errors = [];
  const origError = logger.error;
  logger.error = (msg) => { errors.push(String(msg)); };
  try {
    await ImageProcessor.getInstance().watermark({
      input,
      watermark: logo,
      position: 'top-left',
      output: path.join(dir, 'out.png'),
    });
  } finally {
    logger.error = origError;
  }
  const placed = composites.map((l) => l[0]).find((l) => l && typeof l.left === 'number');
  assert.ok(placed, 'expected a positioned composite layer');
  assert.equal(placed.left, 20);
  assert.equal(placed.top, 20);
  assert.equal(errors.some((m) => m.includes('Placement boundary check failed')), false);
});
