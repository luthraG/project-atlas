import { describe, expect, test, vi } from 'vitest';

const updateCalls: unknown[] = [];
const errorCalls: unknown[][] = [];

vi.mock('./config/env.js', () => ({
  env: new Proxy({}, { get: () => undefined }),
}));

vi.mock('./db/index.js', () => {
  const db = {
    insert: () => ({ values: () => Promise.resolve() }),
    update: (table: unknown) => {
      updateCalls.push(table);
      return { set: () => ({ where: () => Promise.resolve() }) };
    },
    select: () => ({ from: () => Promise.resolve([]) }),
  };
  return { db };
});

vi.mock('./lib/logger.js', () => ({
  logger: {
    error: (...args: unknown[]) => { errorCalls.push(args); },
    warn: () => {},
    info: () => {},
    debug: () => {},
  },
}));

describe('recordClick', () => {
  test('recordClick increments timesClicked for a non-bot client with no parsed browser', async () => {
    const { recordClick } = await import('./modules/links/service.js');
    updateCalls.length = 0;
    errorCalls.length = 0;
    await recordClick({ id: 24 } as any, {
      isBot: false,
      browser: null,
      device: 'desktop',
      os: null,
      userAgent: 'Java-http-client/21.0.4',
      ip: '1.1.1.1',
      referer: null,
      country: null,
    } as any);
    expect(updateCalls.length).toBe(1);
    expect(errorCalls.length).toBe(0);
  });
});
