const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');
const Module = require('node:module');

const root = path.resolve(__dirname, '..');
require('ts-node').register({ transpileOnly: true, compilerOptions: { module: 'commonjs', esModuleInterop: true } });

const errors = [];
let normalizeCalls = 0;
const logger = { info() {}, warn() {}, success() {}, debug() {}, error(m) { errors.push(String(m)); } };

function makeChain() {
  const c = {
    metadata: async () => ({ width: 40, height: 40, format: 'png', hasAlpha: true }),
    resize() { return c; },
    ensureAlpha() { return c; },
    composite() { return c; },
    normalize() { normalizeCalls++; return c; },
    toBuffer: async () => Buffer.from([0]),
    toFile: async (p) => { fs.writeFileSync(p, 'x'); return {}; },
  };
  return c;
}
function fakeSharp() { return makeChain(); }
fakeSharp.default = fakeSharp;
fakeSharp.__esModule = true;

const helpers = {
  generateOutputPath: (input, suffix, output) => output,
  validateFilePath: () => {},
  calculateCropDimensions: () => ({}),
  parseColor: () => ({}),
};

const origLoad = Module._load;
Module._load = function (request, parent, isMain) {
  if (request === 'sharp') return fakeSharp;
  if (request === '../types') return {};
  if (request === '../utils/helpers') return helpers;
  if (request === '../utils/logger') return { logger };
  return origLoad.apply(this, arguments);
};

const { ImageProcessor } = require(path.join(root, 'src', 'services', 'ImageProcessor.ts'));

test('watermark does not log an unmeasured fidelity failure', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'wm-'));
  const input = path.join(dir, 'in.png');
  const wm = path.join(dir, 'wm.png');
  const output = path.join(dir, 'out.png');
  fs.writeFileSync(input, 'x');
  fs.writeFileSync(wm, 'x');
  const result = await ImageProcessor.getInstance().watermark({ input, watermark: wm, output, scale: 0.2, opacity: 0.2, margin: 20 });
  assert.equal(result.success, true);
  assert.ok(normalizeCalls >= 1);
  assert.equal(errors.filter((m) => m.includes('Output fidelity check failed')).length, 0);
});
