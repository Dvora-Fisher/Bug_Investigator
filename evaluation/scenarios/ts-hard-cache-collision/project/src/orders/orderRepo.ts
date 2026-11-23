export interface Order {
  id: number;
  userId: number;
  total: number;
  createdAt: string;
}

/** Stand-in for the orders table. */
export class OrderRepo {
  #orders: Order[] = [];

  add(order: Order): void {
    this.#orders.push(order);
  }

  /** A user's orders, newest first. */
  listForUser(userId: number, offset: number, limit: number): Order[] {
    return this.#orders
      .filter((o) => o.userId === userId)
      .sort((a, b) => b.id - a.id)
      .slice(offset, offset + limit);
  }
}
