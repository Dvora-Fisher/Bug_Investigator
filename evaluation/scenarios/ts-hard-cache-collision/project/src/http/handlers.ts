import { sessionUser } from "../auth/session.ts";
import type { OrderService } from "../orders/orderService.ts";
import { log } from "../util/logger.ts";
import { parsePage } from "../util/pagination.ts";

export interface Request {
  ip: string;
  headers: Record<string, string | undefined>;
  query: Record<string, string | undefined>;
}

export interface Response {
  status: number;
  body: unknown;
}

/** GET /me/orders?page=N */
export function myOrders(orders: OrderService) {
  return (req: Request): Response => {
    const userId = sessionUser(req.headers["x-session"] ?? "");
    if (userId === undefined) return { status: 401, body: { error: "not signed in" } };
    const page = parsePage(req.query.page);
    log("info", `orders page=${page} user=${userId}`);
    return { status: 200, body: orders.ordersPage(userId, page) };
  };
}
