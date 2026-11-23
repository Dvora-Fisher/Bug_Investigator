import { TtlCache } from "./cache/cache.ts";
import { config } from "./config.ts";
import { myOrders } from "./http/handlers.ts";
import { makeRouter } from "./http/router.ts";
import { OrderRepo } from "./orders/orderRepo.ts";
import type { Order } from "./orders/orderRepo.ts";
import { OrderService } from "./orders/orderService.ts";

export function createApp(repo: OrderRepo = new OrderRepo()) {
  const orders = new OrderService(repo, new TtlCache<Order[]>(config.cacheTtlMs));
  return { orders, route: makeRouter({ "/me/orders": myOrders(orders) }) };
}
