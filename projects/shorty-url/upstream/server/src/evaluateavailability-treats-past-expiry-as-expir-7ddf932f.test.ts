import { describe, it, expect, vi, afterEach } from 'vitest';

vi.mock('mysql2', () => ({ default: {}, createPool: () => ({}) }));
vi.mock('mysql2/promise', () => ({ default: { createPool: () => ({}) }, createPool: () => ({}) }));
vi.mock('../src/db/index.js', () => ({ db: {} }));
vi.mock('../src/config/env.js', () => ({ env: {} }));
vi.mock('../src/lib/logger.js', () => ({ logger: { error: () => {}, info: () => {}, warn: () => {} } }));

import { evaluateAvailability } from '../src/modules/links/service.js';

afterEach(() => { vi.useRealTimers(); });

describe('evaluateAvailability', () => {
  it('evaluateAvailability treats past expiry as expired and future expiry as active', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-09-29T14:34:16.442Z'));
    const base = { deletedAt: null, blacklisted: 0, expiredStatus: 0 } as any;
    expect(evaluateAvailability({ ...base, expiresAt: new Date('2026-09-28T01:33:55.000Z') })).toBe('expired');
    expect(evaluateAvailability({ ...base, expiresAt: new Date('2026-10-05T15:33:55.000Z') })).toBe('active');
  });
});
