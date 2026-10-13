require('ts-node/register');
const path = require('node:path');
const test = require('node:test');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const { unifiedArgumentsToParametersArray } = require(path.join(root, 'src/utils/tool-utils.ts'));

test('keeps notifyCustomer false as a query parameter', () => {
  const params = [
    { name: 'ticketId', in: 'path', required: true, schema: { type: 'string' } },
    { name: 'notifyCustomer', in: 'query', required: true, schema: { type: 'boolean' } },
  ];
  const result = unifiedArgumentsToParametersArray({ ticketId: 'T-1', notifyCustomer: false }, params);
  const notify = result.params.find((p) => p.name === 'notifyCustomer');
  assert.ok(notify, 'notifyCustomer should be present');
  assert.equal(notify.in, 'query');
  assert.equal(notify.value, false);
});
