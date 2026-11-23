import { config } from "../config.ts";

const hits = new Map<string, { windowStart: number; count: number }>();

/** Fixed one-minute window per client IP. */
export function allowRequest(ip: string, now: number = Date.now()): boolean {
  const entry = hits.get(ip);
  if (!entry || now - entry.windowStart >= 60_000) {
    hits.set(ip, { windowStart: now, count: 1 });
    return true;
  }
  entry.count += 1;
  return entry.count <= config.rateLimitPerMinute;
}
