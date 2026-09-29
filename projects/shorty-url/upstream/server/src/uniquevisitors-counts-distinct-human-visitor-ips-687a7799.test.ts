import { describe, it, expect, vi } from 'vitest';
import { MySqlDialect } from 'drizzle-orm/mysql-core';

const captured: any[] = [];
vi.mock('../src/db/index.js', () => {
  const chain = (): any => {
    const c: any = {};
    for (const m of ['from', 'where', 'groupBy', 'orderBy', 'limit']) c[m] = () => c;
    c.then = (res: any, rej: any) => Promise.resolve([]).then(res, rej);
    return c;
  };
  return { db: { select: (fields: any) => { captured.push(fields); return chain(); } } };
});
vi.mock('../src/lib/logger.js', () => ({ logger: { error: () => {}, info: () => {}, warn: () => {} } }));

describe('getLinkAnalytics', () => {
  it('uniqueVisitors counts distinct human visitor IPs', async () => {
    const { getLinkAnalytics } = await import('../src/modules/stats/service.ts');
    await getLinkAnalytics(13);
    const totals = captured[0];
    const q = new MySqlDialect().sqlToQuery(totals.uniqueVisitors.getSQL());
    expect(q.sql).toContain('visitor_ip');
    expect(q.sql).not.toContain('visitor_agent');
  });
});
