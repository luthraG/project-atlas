import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('mysql2', () => ({ default: {}, createPool: () => ({}) }));
vi.mock('mysql2/promise', () => ({ default: { createPool: () => ({}) }, createPool: () => ({}) }));
vi.mock('./db/index.js', () => ({ db: {} }));
vi.mock('./config/env.js', () => ({ env: {} }));
vi.mock('./lib/logger.js', () => ({ logger: { error: () => {}, info: () => {}, warn: () => {}, debug: () => {} } }));

import { evaluateAvailability } from './modules/links/service.js';

describe('evaluateAvailability expiry boundary', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-10-06T06:45:00.000Z'));
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('evaluateAvailability treats past expiresAt as expired and future as active', () => {
    const base = { deletedAt: null, blacklisted: 0, expiredStatus: 0 } as any;
    const future = { ...base, expiresAt: new Date('2026-10-12T07:45:05.000Z') };
    const past = { ...base, expiresAt: new Date('2026-10-04T11:45:05.000Z') };
    expect(evaluateAvailability(future)).toBe('active');
    expect(evaluateAvailability(past)).toBe('expired');
  });
});
