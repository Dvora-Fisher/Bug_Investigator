export type Role = "customer" | "support" | "admin";

/** Support and admins may look at any customer's orders; customers only at their own. */
export function canViewOrders(role: Role, viewerId: number, ownerId: number): boolean {
  return role !== "customer" || viewerId === ownerId;
}
