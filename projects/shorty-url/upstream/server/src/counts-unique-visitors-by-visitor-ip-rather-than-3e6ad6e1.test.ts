import { it, expect, vi } from 'vitest';

const captured = vi.hoisted(() => [] as string[]);

vi.mock('mysql2', () => ({ default: {}, createPool: () => ({}) }));
vi.mock('mysql2/promise', () => ({ default: { createPool: () => ({}) }, createPool: () => ({}) }));
vi.mock('../src/lib/logger.js', () => ({
  logger: { error: vi.fn(), warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}));
vi.mock('../src/db/index.js', async () => {
  const { drizzle } = await import('drizzle-orm/mysql-proxy');
  const db = drizzle(async (query: string) => {
    captured.push(query);
    return { rows: [] };
  });
  return { db };
});

it('counts unique visitors by visitor IP rather than user-agent', async () => {
  const { getLinkAnalytics } = await import('../src/modules/stats/service.js');
  await getLinkAnalytics(13);
  const totalsQuery = captured.find((q) => /count\(distinct/i.test(q));
  expect(totalsQuery).toBeDefined();
  expect(totalsQuery).toMatch(/count\(distinct [^)]*visitor_ip/i);
  expect(totalsQuery).not.toMatch(/visitor_agent/i);
});
