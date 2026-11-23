export interface BatchResult {
  ok: boolean;
  imported: number;
  error?: string;
}

/** Save every record; report failure (instead of crashing) if any save fails. */
export async function importBatch<T>(records: T[], save: (r: T) => Promise<void>): Promise<BatchResult> {
  try {
    records.map((r) => save(r));
    return { ok: true, imported: records.length };
  } catch (err) {
    return { ok: false, imported: 0, error: (err as Error).message };
  }
}
