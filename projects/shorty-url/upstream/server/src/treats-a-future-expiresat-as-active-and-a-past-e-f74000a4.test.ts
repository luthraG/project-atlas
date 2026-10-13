import { it, expect, vi, afterEach } from 'vitest';

vi.mock('mysql2/promise', () => {
  const pool = { query: vi.fn(), execute: vi.fn(), getConnection: vi.fn(), end: vi.fn(), on: vi.fn(), promise: () => pool };
  const api = { createPool: () => pool, createConnection: async () => pool };
  return { ...api, default: api };
});
vi.mock('mysql2', () => {
  const pool = { query: vi.fn(), execute: vi.fn(), getConnection: vi.fn(), end: vi.fn(), on: vi.fn(), promise: () => pool };
  const api = { createPool: () => pool, createConnection: () => pool };
  return { ...api, default: api };
});

import { evaluateAvailability } from './modules/links/service.js';

afterEach(() => {
  vi.useRealTimers();
});

it('treats a future expiresAt as active and a past expiresAt as expired', () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date('2026-10-13T04:56:34.659Z'));
  const base = { deletedAt: null, blacklisted: 0, expiredStatus: 0 };
  const future = { ...base, expiresAt: new Date('2026-10-19T05:56:33.000Z') } as any;
  const past = { ...base, expiresAt: new Date('2026-10-11T15:56:33.000Z') } as any;
  expect(evaluateAvailability(future)).toBe('active');
  expect(evaluateAvailability(past)).toBe('expired');
});
