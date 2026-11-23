import { allowRequest } from "./middleware.ts";
import type { Request, Response } from "./handlers.ts";

export type Handler = (req: Request) => Response;

export function makeRouter(routes: Record<string, Handler>) {
  return (path: string, req: Request): Response => {
    if (!allowRequest(req.ip)) return { status: 429, body: { error: "slow down" } };
    const handler = routes[path];
    return handler ? handler(req) : { status: 404, body: { error: "no such route" } };
  };
}
