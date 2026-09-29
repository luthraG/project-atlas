import { it, expect, vi, afterEach } from 'vitest';

vi.mock('../src/db/index.js', () => ({ db: {} }));
vi.mock('../src/config/env.js', () => ({ env: {} }));
vi.mock('../src/lib/logger.js', () => ({ logger: { error: vi.fn(), info: vi.fn(), warn: vi.fn(), debug: vi.fn() } }));

import { evaluateAvailability } from '../src/modules/links/service.js';

afterEach(() => {
  vi.useRealTimers();
});

it('classifies expiry by the boundary used by the redirect controller', () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date('2026-09-29T08:42:04.659Z'));
  const base = { deletedAt: null, blacklisted: 0, expiredStatus: 0 } as any;
  const future = { ...base, expiresAt: new Date('2026-10-05T09:42:03.000Z') };
  const past = { ...base, expiresAt: new Date('2026-09-27T19:42:03.000Z') };
  expect(evaluateAvailability(future)).toBe('active');
  expect(evaluateAvailability(past)).toBe('expired');
});
