import { test, expect, vi } from 'vitest';

const state = vi.hoisted(() => ({ updates: [] as Array<{ set: Record<string, unknown> | null }> }));

vi.mock('../src/config/env.js', () => ({
  env: new Proxy({}, { get: (_t, p) => (p === 'then' ? undefined : 'http://localhost') }),
}));
vi.mock('../src/lib/logger.js', () => ({
  logger: { error: vi.fn(), warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}));
vi.mock('../src/db/index.js', () => ({
  db: {
    insert: () => ({ values: () => Promise.resolve() }),
    update: () => {
      const call = { set: null as Record<string, unknown> | null };
      state.updates.push(call);
      return {
        set: (v: Record<string, unknown>) => {
          call.set = v;
          return { where: () => Promise.resolve() };
        },
      };
    },
    select: () => ({ from: () => Promise.resolve([]) }),
  },
}));

test('counts a non-bot click whose browser could not be classified', async () => {
  const { recordClick } = await import('../src/modules/links/service.js');
  const client = {
    ip: '203.0.113.1',
    userAgent: 'curl/8',
    referer: null,
    country: null,
    device: 'desktop',
    browser: null,
    os: null,
    isBot: false,
  };
  await recordClick({ id: 42 } as never, client as never);
  expect(state.updates.length).toBe(1);
  expect(state.updates[0].set).toHaveProperty('timesClicked');
  expect(state.updates[0].set).toHaveProperty('lastClickedAt');
});
