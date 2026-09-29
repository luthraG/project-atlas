import { describe, it, expect, vi, beforeEach } from 'vitest';

const updateCalls: unknown[] = [];
vi.mock('../src/db/index.js', () => ({
  db: {
    insert: () => ({ values: () => Promise.resolve() }),
    update: (table: unknown) => {
      updateCalls.push(table);
      return { set: () => ({ where: () => Promise.resolve() }) };
    },
    select: () => ({ from: () => Promise.resolve([]) }),
  },
}));
const errorSpy = vi.fn();
vi.mock('../src/lib/logger.js', () => ({
  logger: { error: errorSpy, warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}));
vi.mock('../src/config/env.js', () => ({ env: new Proxy({}, { get: () => 'test' }) }));

describe('recordClick', () => {
  beforeEach(() => {
    updateCalls.length = 0;
    errorSpy.mockClear();
  });

  it('counts a non-bot click whose browser is null', async () => {
    const { recordClick } = await import('../src/modules/links/service.js');
    const client = {
      ip: '203.0.113.5',
      userAgent: 'UnknownAgent/1.0',
      referer: null,
      country: null,
      device: 'desktop',
      browser: null,
      os: null,
      isBot: false,
    };
    await recordClick({ id: 7 } as any, client as any);
    expect(updateCalls.length).toBe(1);
    const msgs = errorSpy.mock.calls.map((c) => c[1]);
    expect(msgs).not.toContain('click classification produced an incomplete counter update');
  });
});
