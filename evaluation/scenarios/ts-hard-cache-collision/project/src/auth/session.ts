import { randomUUID } from "node:crypto";
import { config } from "../config.ts";
import { decodeToken } from "./token.ts";

export interface Session {
  userId: number;
  expires: number;
}

// One store for the whole process; session ids are random UUIDs.
const sessions = new Map<string, Session>();

export function openSession(token: string, now: number = Date.now()): string {
  const claims = decodeToken(token);
  if (claims.exp * 1000 <= now) throw new Error("token expired");
  const id = randomUUID();
  sessions.set(id, { userId: claims.sub, expires: now + config.sessionTtlMs });
  return id;
}

export function sessionUser(id: string, now: number = Date.now()): number | undefined {
  const session = sessions.get(id);
  if (!session || session.expires <= now) return undefined;
  return session.userId;
}

export function closeSession(id: string): void {
  sessions.delete(id);
}
