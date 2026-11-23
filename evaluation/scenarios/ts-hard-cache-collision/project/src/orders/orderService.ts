import { TtlCache } from "../cache/cache.ts";
import { config } from "../config.ts";
import { pageBounds } from "../util/pagination.ts";
import type { Order, OrderRepo } from "./orderRepo.ts";

export class OrderService {
  repo: OrderRepo;
  cache: TtlCache<Order[]>;

  constructor(repo: OrderRepo, cache: TtlCache<Order[]>) {
    this.repo = repo;
    this.cache = cache;
  }

  /** One page of a user's orders. Pages are cached for config.cacheTtlMs. */
  ordersPage(userId: number, page: number): Order[] {
    const key = `orders:${userId}${page}`;
    const cached = this.cache.get(key);
    if (cached) return cached;
    const { offset, limit } = pageBounds(page, config.pageSize);
    const orders = this.repo.listForUser(userId, offset, limit);
    this.cache.set(key, orders);
    return orders;
  }

  /** Called after a new order is placed. The cache has no prefix delete, so drop everything. */
  invalidate(): void {
    this.cache.clear();
  }
}
