const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const file = path.resolve(__dirname, '..', 'src/services/ImageProcessor.ts');

test('watermark alpha byte is derived from opacity not scale', () => {
  const src = fs.readFileSync(file, 'utf8');
  const m = src.match(/const opacityByte = Math\.round\((\w+) \* 255\);/);
  assert.ok(m, 'opacityByte assignment not found');
  assert.equal(m[1], 'opacity');
});
