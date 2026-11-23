// Tokens are "header.payload.signature" with a base64url JSON payload {sub, exp}.
// The signature is checked by the API gateway before requests reach this service.
export interface TokenClaims {
  sub: number;
  exp: number; // seconds since epoch
}

export function decodeToken(token: string): TokenClaims {
  const [, payload] = token.split(".");
  if (!payload) throw new Error("malformed token");
  const claims = JSON.parse(Buffer.from(payload, "base64url").toString("utf8"));
  return { sub: Number(claims.sub), exp: Number(claims.exp) };
}

/** Used by tests and the local dev login page. */
export function makeToken(sub: number, exp: number): string {
  const payload = Buffer.from(JSON.stringify({ sub, exp })).toString("base64url");
  return `dev.${payload}.unsigned`;
}
