'use strict';
// Reproduces the watermark opacity defect: the 1x1 RGBA overlay that sets the
// watermark's alpha must carry Math.round(opacity * 255), not Math.round(scale * 255).
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const Module = require('node:module');

// This file runs from <service root>/.kausalis-tests/.
const root = path.resolve(__dirname, '..');
const work = fs.mkdtempSync(path.join(os.tmpdir(), 'watermark-opacity-'));
const inputPath = path.join(work, 'input.png');
const watermarkPath = path.join(work, 'mark.png');
const outputPath = path.join(work, 'out.png');
process.env.IMAGE_SERVICE_LOG_DIR = path.join(work, 'logs');

// sharp is replaced by a recording fake, so no native binary is loaded.
const sharpCalls = [];
function fakeSharp(input) {
  const image = {};
  const chain = name => (...args) => { sharpCalls.push({ input, name, args }); return image; };
  for (const name of ['resize', 'ensureAlpha', 'composite', 'normalize', 'png', 'jpeg', 'webp', 'toFormat']) {
    image[name] = chain(name);
  }
  image.metadata = async () => input === watermarkPath
    ? { width: 200, height: 100, format: 'png', channels: 4, hasAlpha: true }
    : { width: 1000, height: 800, format: 'png', channels: 4, hasAlpha: true };
  image.toBuffer = async () => Buffer.from('fake-watermark');
  image.toFile = async file => { fs.writeFileSync(file, 'fake'); return { width: 1000, height: 800, size: 4 }; };
  return image;
}
fakeSharp.default = fakeSharp;
const sharpPath = require.resolve('sharp', { paths: [root] });
const sharpModule = new Module(sharpPath, module);
sharpModule.filename = sharpPath;
sharpModule.loaded = true;
sharpModule.exports = fakeSharp;
require.cache[sharpPath] = sharpModule;

// The service's own TypeScript, loaded through its own ts-node devDependency.
require(require.resolve('ts-node', { paths: [root] })).register({
  project: path.join(root, 'tsconfig.json'),
  transpileOnly: true,
  compilerOptions: { module: 'commonjs' },
});
const { logger } = require(path.join(root, 'src/utils/logger'));
const logged = [];
for (const level of ['info', 'success', 'warning', 'error', 'debug']) {
  logger[level] = message => { logged.push({ level, message: String(message) }); };
}
const { ImageProcessor } = require(path.join(root, 'src/services/ImageProcessor'));

test('watermark alpha byte follows opacity, not scale', async () => {
  try {
    fs.writeFileSync(inputPath, 'input');
    fs.writeFileSync(watermarkPath, 'mark');
    const opacity = 0.5, scale = 0.2;
    const result = await ImageProcessor.getInstance().watermark({ input: inputPath, watermark: watermarkPath,
      output: outputPath, opacity, scale, position: 'bottom-right', margin: 20 });
    assert.equal(result.success, true, `watermark did not complete: ${result.error}`);

    const overlays = sharpCalls.filter(call => call.name === 'composite')
      .flatMap(call => call.args[0])
      .filter(layer => layer && Buffer.isBuffer(layer.input) && layer.input.length === 4
        && layer.raw && layer.raw.channels === 4);
    assert.equal(overlays.length, 1, 'expected exactly one 1x1 RGBA alpha overlay');

    const expected = Math.round(opacity * 255);
    const rendered = overlays[0].input[3];
    assert.equal(rendered, expected,
      `overlay alpha is ${rendered}/255; opacity ${opacity} requires ${expected}/255`);

    const opacityErrors = logged.filter(entry => entry.level === 'error'
      && entry.message.includes('Opacity verification failed'));
    assert.deepEqual(opacityErrors, [], 'the service logged its own opacity verification failure');
  } finally {
    fs.rmSync(work, { recursive: true, force: true });
  }
});