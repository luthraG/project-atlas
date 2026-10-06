import { describe, it, expect, vi } from 'vitest';

const calls = vi.hoisted(() => ({ inserts: 0, updates: 0 }));

vi.mock('./config/env.js', () => ({ env: {} }));
vi.mock('./lib/logger.js', () => ({
  logger: { error: vi.fn(), warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}));
vi.mock('./db/index.js', () => ({
  db: {
    insert: () => ({ values: async () => { calls.inserts += 1; } }),
    update: () => ({ set: () => ({ where: async () => { calls.updates += 1; } }) }),
    select: () => ({ from: async () => [] }),
  },
}));

import { recordClick } from './modules/links/service.js';

describe('recordClick', () => {
  it('increments times_clicked for a non-bot click with null browser', async () => {
    calls.inserts = 0;
    calls.updates = 0;
    const client = {
      ip: '203.0.113.1',
      userAgent: 'CustomClient/1.0',
      referer: null,
      country: null,
      device: 'desktop',
      browser: null,
      os: null,
      isBot: false,
    };
    await recordClick({ id: 24 } as any, client as any);
    expect(calls.inserts).toBe(1);
    expect(calls.updates).toBe(1);
  });
});
