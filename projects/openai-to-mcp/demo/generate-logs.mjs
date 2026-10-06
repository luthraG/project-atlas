// Drives the openai-to-mcp server the way a support agent's MCP client would, against the local
// Helpdesk API stand-in, and keeps the server's log as ./logs/openai-to-mcp.log.
//   node generate-logs.mjs [--minutes 4]
// Needs `npm ci && npm run build` in ../upstream first; run.sh does both.
import { createRequire } from 'node:module';
import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, renameSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { randomBytes } from 'node:crypto';
import { startHelpdeskApi } from './mock-helpdesk-api.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const upstream = join(here, '..', 'upstream');
const require = createRequire(join(upstream, 'package.json'));
const { Client } = require('@modelcontextprotocol/sdk/client/index.js');
const { StdioClientTransport } = require('@modelcontextprotocol/sdk/client/stdio.js');

const minutesArg = process.argv.indexOf('--minutes');
const minutes = minutesArg > 0 ? Number(process.argv[minutesArg + 1]) : 4;
if (!(minutes > 0 && minutes <= 30)) throw new Error('--minutes must be between 0 and 30');
const entry = join(upstream, 'dist', 'src', 'index.js');
if (!existsSync(entry)) throw new Error(`build the server first: ${entry} is missing`);

// Seeded, so two runs send the same sequence of calls.
let seed = 20261006;
const rand = () => (seed = (Math.imul(seed, 1103515245) + 12345) >>> 0) / 2 ** 32;
const pick = values => values[Math.floor(rand() * values.length)];
const ticket = () => `T-${1040 + Math.floor(rand() * 60)}`;

const plan = [
  [3.0, () => ['listTickets', { status: [pick(['open', 'pending', 'closed'])], limit: pick([10, 20, 50]) }]],
  [1.2, () => ['listTickets', { status: pick([['open', 'pending'], ['pending', 'closed']]), limit: 20 }]],
  [1.5, () => ['listTickets', { fields: pick([['id', 'subject', 'status'], ['id', 'assignee', 'updatedAt']]), limit: 25 }]],
  [2.0, () => ['getTicket', { ticketId: ticket() }]],
  [1.5, () => ['closeTicket', { ticketId: ticket(), notifyCustomer: true, resolution: 'fixed' }]],
  [1.4, () => ['closeTicket', { ticketId: ticket(), notifyCustomer: false, resolution: pick(['duplicate', 'wont_fix']) }]],
];
const totalWeight = plan.reduce((sum, [weight]) => sum + weight, 0);
const nextCall = () => {
  let r = rand() * totalWeight;
  for (const [weight, make] of plan) { if ((r -= weight) < 0) return make(); }
  return plan[0][1]();
};

const clientId = 'atlas-desk-agent', clientSecret = randomBytes(16).toString('hex');
const api = await startHelpdeskApi({ clientId, clientSecret });
const baseUrl = `http://127.0.0.1:${api.port}`;
const rawDir = mkdtempSync(join(tmpdir(), 'openai-to-mcp-logs-'));
const transport = new StdioClientTransport({
  command: process.execPath,
  args: [entry, '--spec', join(here, 'helpdesk-api.yaml'), '--base-url', baseUrl, '--log-level', 'info',
    '--oauth-client-id', clientId, '--oauth-client-secret', clientSecret, '--oauth-token-url', `${baseUrl}/oauth/token`],
  env: { ...process.env, OPENAPI_MCP_LOG_DIR: rawDir },
  stderr: 'ignore',
});
const client = new Client({ name: 'atlas-desk-agent', version: '1.0.0' });
await client.connect(transport);
const tools = (await client.listTools()).tools.map(tool => tool.name);
console.log(`[generate-logs] server up with tools ${tools.join(', ')}; sending traffic for ${minutes} min`);

const deadline = Date.now() + minutes * 60_000;
const outcomes = {};
while (Date.now() < deadline) {
  const [name, args] = nextCall();
  const result = await client.callTool({ name, arguments: args });
  const status = JSON.parse(result.content[0].text).statusCode;
  outcomes[`${name} ${status}`] = (outcomes[`${name} ${status}`] ?? 0) + 1;
  await new Promise(resolve => setTimeout(resolve, 1500 + rand() * 3000));
}
await client.close();
await new Promise(resolve => setTimeout(resolve, 1000));
api.server.close();

const logs = join(here, 'logs');
mkdirSync(join(logs, 'archive'), { recursive: true });
const out = join(logs, 'openai-to-mcp.log');
if (existsSync(out)) renameSync(out, join(logs, 'archive', `openai-to-mcp-${new Date().toISOString().replace(/[:.]/g, '')}.log`));
const raw = readdirSync(rawDir).filter(name => /^app-.*\.log$/.test(name)).sort();
const text = raw.map(name => readFileSync(join(rawDir, name), 'utf8')).join('');
writeFileSync(out, text);
rmSync(rawDir, { recursive: true, force: true });

const errors = {};
for (const line of text.split('\n').filter(Boolean)) {
  const record = JSON.parse(line);
  if (record.level === 'error') errors[record.message] = (errors[record.message] ?? 0) + 1;
}
console.log('[generate-logs] tool results', outcomes);
console.log('[generate-logs] error records', errors);
console.log(`[generate-logs] wrote ${out} (${text.split('\n').filter(Boolean).length} records)`);
