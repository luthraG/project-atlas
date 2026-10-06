// A small stand-in for the Helpdesk API described in helpdesk-api.yaml, with a client-credentials
// token endpoint. It holds tickets in memory and validates requests the way the real API does.
import { createServer } from 'node:http';
import { randomBytes } from 'node:crypto';

const STATUSES = ['open', 'pending', 'closed'];
const FIELDS = ['id', 'subject', 'status', 'priority', 'assignee', 'updatedAt'];
const TOKEN_GRANTS_PER_MINUTE = 6;
const TOKEN_LIFETIME_SECONDS = 3600;

export function startHelpdeskApi({ clientId, clientSecret, port = 0 }) {
  const tokens = new Map();
  const grants = [];
  const tickets = new Map();
  const subjects = ['Cannot reset password', 'Invoice shows wrong VAT', 'Export stuck at 99%', 'SSO login loops',
    'Webhook retries never stop', 'Billing address not saved', 'CSV import drops rows', 'Mobile app crashes on launch'];
  for (let i = 0; i < 60; i++) {
    const id = `T-${1040 + i}`;
    tickets.set(id, { id, subject: subjects[i % subjects.length], status: STATUSES[i % 3], priority: ['low', 'normal', 'high'][i % 3],
      assignee: ['maya', 'oskar', 'lena', 'dev'][i % 4], updatedAt: new Date(Date.now() - i * 3_600_000).toISOString() });
  }

  const send = (res, status, body) => { res.writeHead(status, { 'content-type': 'application/json' }); res.end(JSON.stringify(body)); };
  const readBody = req => new Promise(resolve => { let b = ''; req.on('data', c => { b += c; }); req.on('end', () => resolve(b)); });

  const server = createServer(async (req, res) => {
    const url = new URL(req.url, 'http://localhost');
    if (req.method === 'POST' && url.pathname === '/oauth/token') {
      await readBody(req);
      const basic = 'Basic ' + Buffer.from(`${clientId}:${clientSecret}`).toString('base64');
      if (req.headers.authorization !== basic) return send(res, 401, { error: 'invalid_client' });
      const now = Date.now();
      while (grants.length && grants[0] <= now - 60_000) grants.shift();
      if (grants.length >= TOKEN_GRANTS_PER_MINUTE)
        return send(res, 429, { error: 'slow_down', error_description: `At most ${TOKEN_GRANTS_PER_MINUTE} token grants per minute per client` });
      grants.push(now);
      const token = randomBytes(18).toString('base64url');
      tokens.set(token, now + TOKEN_LIFETIME_SECONDS * 1000);
      return send(res, 200, { access_token: token, token_type: 'Bearer', expires_in: TOKEN_LIFETIME_SECONDS });
    }

    const bearer = /^Bearer (.+)$/.exec(req.headers.authorization ?? '')?.[1];
    if (!bearer || !(tokens.get(bearer) > Date.now())) return send(res, 401, { message: 'A valid bearer token is required' });

    if (req.method === 'GET' && url.pathname === '/tickets') {
      const status = url.searchParams.getAll('status');
      for (const value of status)
        if (!STATUSES.includes(value)) return send(res, 422, { message: `status must be one of [${STATUSES.join(', ')}]; got "${value}"` });
      const fieldValues = url.searchParams.getAll('fields');
      if (fieldValues.length > 1) return send(res, 400, { message: 'fields must be sent once, as a comma-separated list' });
      const fields = fieldValues.length ? fieldValues[0].split(',') : FIELDS;
      for (const value of fields)
        if (!FIELDS.includes(value)) return send(res, 422, { message: `fields must be drawn from [${FIELDS.join(', ')}]; got "${value}"` });
      const limit = url.searchParams.has('limit') ? Number(url.searchParams.get('limit')) : 20;
      if (!Number.isInteger(limit) || limit < 1 || limit > 100) return send(res, 422, { message: 'limit must be an integer from 1 to 100' });
      const rows = [...tickets.values()].filter(t => !status.length || status.includes(t.status)).slice(0, limit)
        .map(t => Object.fromEntries(fields.map(f => [f, t[f]])));
      return send(res, 200, { tickets: rows, count: rows.length });
    }

    const one = /^\/tickets\/([A-Za-z0-9-]+)(\/close)?$/.exec(url.pathname);
    if (one) {
      const ticket = tickets.get(one[1]);
      if (!ticket) return send(res, 404, { message: `ticket ${one[1]} not found` });
      if (req.method === 'GET' && !one[2]) return send(res, 200, ticket);
      if (req.method === 'POST' && one[2]) {
        await readBody(req);
        const notify = url.searchParams.get('notifyCustomer');
        if (notify === null) return send(res, 400, { message: 'notifyCustomer is required' });
        if (notify !== 'true' && notify !== 'false') return send(res, 400, { message: 'notifyCustomer must be true or false' });
        const resolution = url.searchParams.get('resolution') ?? 'fixed';
        ticket.status = 'closed'; ticket.updatedAt = new Date().toISOString();
        return send(res, 200, { ...ticket, resolution, customerNotified: notify === 'true' });
      }
    }
    return send(res, 404, { message: 'no such route' });
  });

  return new Promise(resolve => server.listen(port, '127.0.0.1', () => resolve({ server, port: server.address().port })));
}
