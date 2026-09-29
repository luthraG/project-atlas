import { test, expect, vi, afterEach } from 'vitest';

vi.mock('../src/db/index.js', () => ({ db: {} }));
vi.mock('mysql2', () => ({ default: {} }));
vi.mock('mysql2/promise', () => ({ default: { createPool: () => ({}) }, createPool: () => ({}) }));

afterEach(() => {
  vi.useRealTimers();
});

test('evaluateAvailability treats past expiry as expired and future expiry as active', async () => {
  vi.useFakeTimers({ now: new Date('2026-09-29T12:16:21.659Z') });
  const { evaluateAvailability } = await import('../src/modules/links/service.js');
  const base = { deletedAt: null, blacklisted: 0, expiredStatus: 0 } as any;
  expect(evaluateAvailability({ ...base, expiresAt: new Date('2026-10-05T13:16:20.000Z') })).toBe('active');
  expect(evaluateAvailability({ ...base, expiresAt: new Date('2026-09-27T23:16:20.000Z') })).toBe('expired');
});
