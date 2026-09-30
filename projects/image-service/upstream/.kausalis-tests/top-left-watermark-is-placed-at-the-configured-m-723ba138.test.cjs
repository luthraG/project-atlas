'use strict';
const test = require('node:test');
const assert = require('node:assert');
const path = require('path');
const fs = require('fs');
const os = require('os');
const Module = require('module');

// Fake the native sharp module only.
const compositeCalls = [];
const WATERMARK_BUFFER = Buffer.from('fake-watermark');
function makePipeline(src) {
  const isWatermark = typeof src === 'string' && path.basename(src) === 'wm.png';
  const p = {
    metadata: async () => {
      if (isWatermark) return { width: 500, height: 250, format: 'png' };
      return { width: 1000, height: 800, format: 'png' };
    },
    resize() { return p; },
    ensureAlpha() { return p; },
    normalize() { return p; },
    composite(arr) { compositeCalls.push(arr); return p; },
    toBuffer: async () => WATERMARK_BUFFER,
    toFile: async (out) => { fs.writeFileSync(out, 'x'); return {}; },
  };
  return p;
}
function fakeSharp(src) { return makePipeline(src); }
fakeSharp.default = fakeSharp;
fakeSharp.__esModule = true;

const origLoad = Module._load;
Module._load = function (request, parent, isMain) {
  if (request === 'sharp') return fakeSharp;
  return origLoad.apply(this, arguments);
};

require('ts-node').register({ transpileOnly: true, compilerOptions: { module: 'commonjs', esModuleInterop: true } });
const { ImageProcessor } = require(path.join(__dirname, '..', 'src', 'services', 'ImageProcessor.ts'));

test('top-left watermark is placed at the configured margin', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'placement-test-'));
  const input = path.join(dir, 'input.png');
  const wm = path.join(dir, 'wm.png');
  const output = path.join(dir, 'out.png');
  fs.writeFileSync(input, 'x');
  fs.writeFileSync(wm, 'x');

  const result = await ImageProcessor.getInstance().watermark({
    input,
    watermark: wm,
    output,
    position: 'top-left',
    margin: 20,
    scale: 0.2,
    opacity: 0.2,
  });
  assert.strictEqual(result.success, true, 'watermark failed before placement: ' + result.error);

  const finalCall = compositeCalls.find((arr) => arr[0] && arr[0].blend === 'over');
  assert.ok(finalCall, 'final composite not called');
  // watermarkWidth = 1000 * 0.2 = 200; unfixed code adds round(200*0.01)=2 => 22.
  assert.strictEqual(finalCall[0].left, 20, 'left offset should equal configured margin');
  assert.strictEqual(finalCall[0].top, 20, 'top offset should equal configured margin');
});
