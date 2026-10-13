const path = require('node:path');
const os = require('node:os');
const fs = require('node:fs');
process.env.OPENAPI_MCP_LOG_DIR = fs.mkdtempSync(path.join(os.tmpdir(), 'mcp-log-'));
try { require('tsx/cjs'); } catch (e) { require('ts-node/register/transpile-only'); }
const test = require('node:test');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const { unifiedArgumentsToParametersArray } = require(path.join(root, 'src/utils/tool-utils.ts'));

test('keeps status query array unjoined while fields explode false is joined', () => {
  const params = [
    { name: 'status', in: 'query', schema: { type: 'array', items: { type: 'string' } } },
    { name: 'fields', in: 'query', explode: false, schema: { type: 'array', items: { type: 'string' } } }
  ];
  const result = unifiedArgumentsToParametersArray({ status: ['open', 'pending'], fields: ['id', 'subject'] }, params);
  const status = result.params.find(p => p.name === 'status');
  const fields = result.params.find(p => p.name === 'fields');
  assert.deepEqual(status.value, ['open', 'pending']);
  assert.equal(fields.value, 'id,subject');
});
