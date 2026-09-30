import { describe, it, expect, vi } from 'vitest';

const updateCalls: unknown[] = [];
const insertCalls: unknown[] = [];

vi.mock('../src/db/index.js', () => ({
  db: {
    insert: (table: unknown) => ({
      values: (v: unknown) => { insertCalls.push({ table, v }); return Promise.resolve(); },
    }),
    update: (table: unknown) => ({
      set: (s: unknown) => ({
        where: (w: unknown) => { updateCalls.push({ table, s, w }); return Promise.resolve(); },
      }),
    }),
    select: () => ({ from: () => Promise.resolve([]) }),
  },
}));

vi.mock('../src/lib/logger.js', () => ({
  logger: { error: vi.fn(), warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}));

vi.mock('../src/config/env.js', () => ({
  env: new Proxy({}, { get: () => 'test' }),
}));

describe('recordClick', () => {
  it('increments timesClicked for a non-bot click with an unclassified browser', async () => {
    const { recordClick } = await import('../src/modules/links/service.ts');
    const client = {
      ip: '1.1.1.1', userAgent: 'x', referer: null, country: null,
      device: null, browser: null, os: null, isBot: false,
    } as any;
    await recordClick({ id: 7 } as any, client);
    expect(insertCalls.length).toBe(1);
    expect(updateCalls.length).toBe(1);
  });
});
