require('ts-node').register({ transpileOnly: true });
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');
const fs = require('fs');
const os = require('os');
const Module = require('module');

const root = path.resolve(__dirname, '..');
const composites = [];
const dims = {};
function makeChain(p) {
  const target = {};
  const proxy = new Proxy(target, {
    get(_t, prop) {
      if (prop === 'then') return undefined;
      if (prop === 'metadata') return async () => ({ width: (dims[p] || {}).width || 10, height: (dims[p] || {}).height || 10, format: 'png', channels: 4 });
      if (prop === 'toBuffer') return async () => Buffer.from([0]);
      if (prop === 'toFile') return async (out) => { fs.writeFileSync(out, 'x'); dims[out] = { width: 1000, height: 1000 }; return {}; };
      if (prop === 'composite') return (arr) => { composites.push(arr); return proxy; };
      return () => proxy;
    },
  });
  return proxy;
}
function fakeSharp(p) { return makeChain(p); }
fakeSharp.default = fakeSharp;
const origLoad = Module._load;
Module._load = function (request, parent, isMain) {
  if (request === 'sharp') return fakeSharp;
  return origLoad.apply(this, arguments);
};

test('watermark bottom-right placement uses configured margin', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'wm-'));
  const input = path.join(dir, 'in.png');
  const mark = path.join(dir, 'mark.png');
  const output = path.join(dir, 'out.png');
  fs.writeFileSync(input, 'x');
  fs.writeFileSync(mark, 'x');
  dims[input] = { width: 1000, height: 1000 };
  dims[mark] = { width: 100, height: 100 };
  const mod = require(path.join(root, 'src/services/ImageProcessor.ts'));
  const Proc = mod.ImageProcessor || mod.default;
  const proc = new Proc();
  await proc.watermark({ input, watermark: mark, output, scale: 0.2, margin: 20, position: 'bottom-right', opacity: 0.2 });
  const placed = composites.map((c) => c[0]).find((c) => typeof c.left === 'number');
  assert.ok(placed, 'final composite was called');
  assert.equal(placed.left, 780);
  assert.equal(placed.top, 780);
});
