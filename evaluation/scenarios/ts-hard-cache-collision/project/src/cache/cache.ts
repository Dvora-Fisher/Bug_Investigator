/** Small in-process cache with a time-to-live per entry. Shared by all requests of one server process. */
export class TtlCache<T> {
  #entries = new Map<string, { value: T; expires: number }>();
  ttlMs: number;
  now: () => number;

  constructor(ttlMs: number, now: () => number = Date.now) {
    this.ttlMs = ttlMs;
    this.now = now;
  }

  get(key: string): T | undefined {
    const entry = this.#entries.get(key);
    if (!entry) return undefined;
    if (entry.expires <= this.now()) {
      this.#entries.delete(key);
      return undefined;
    }
    return entry.value;
  }

  set(key: string, value: T): void {
    this.#entries.set(key, { value, expires: this.now() + this.ttlMs });
  }

  clear(): void {
    this.#entries.clear();
  }

  get size(): number {
    return this.#entries.size;
  }
}
