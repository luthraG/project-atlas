import { describe, it, expect, vi, beforeEach } from 'vitest';

const calls = vi.hoisted(() => ({ update: 0, insert: 0, errors: [] as string[] }));

vi.mock('../src/config/env.js', () => ({ env: {} }));
vi.mock('../src/db/index.js', () => ({
  db: {
    insert: () => { calls.insert += 1; return { values: async () => undefined }; },
    update: () => { calls.update += 1; return { set: () => ({ where: async () => undefined }) }; },
  },
}));
vi.mock('../src/lib/logger.js', () => ({
  logger: {
    error: (_o: unknown, msg: string) => { calls.errors.push(msg); },
    warn: () => {}, info: () => {}, debug: () => {},
  },
}));

import { recordClick } from '../src/modules/links/service.js';

describe('recordClick', () => {
  beforeEach(() => { calls.update = 0; calls.insert = 0; calls.errors = []; });

  it('increments timesClicked for a non-bot click with null browser', async () => {
    const client = { isBot: false, browser: null, ip: '1.1.1.1', userAgent: 'x', referer: null, country: null, device: null, os: null };
    await recordClick({ id: 7 } as any, client as any);
    expect(calls.insert).toBe(1);
    expect(calls.update).toBe(1);
    expect(calls.errors).not.toContain('click classification produced an incomplete counter update');
  });
});
