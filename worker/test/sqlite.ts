import { DatabaseSync } from "node:sqlite";

/** Real SQLite with the small synchronous Cloudflare storage surface used here.
 * The deployed Worker journey additionally exercises workerd's storage itself.
 */
export function sqliteStorage(): { storage: DurableObjectStorage; close: () => void } {
  const database = new DatabaseSync(":memory:");
  const storage = {
    sql: {
      exec(query: string, ...bindings: (string | number | Uint8Array)[]) {
        if (bindings.length === 0 && query.includes(";")) {
          database.exec(query);
          return { toArray: () => [] };
        }
        const rows = database.prepare(query).all(...bindings).map((row) =>
          Object.fromEntries(Object.entries(row).map(([key, value]) => [
            key, value instanceof Uint8Array ? value.slice().buffer : value,
          ])),
        );
        return { toArray: () => rows };
      },
    },
    transactionSync<T>(operation: () => T): T {
      database.exec("BEGIN");
      try {
        const result = operation();
        database.exec("COMMIT");
        return result;
      } catch (error) {
        database.exec("ROLLBACK");
        throw error;
      }
    },
  } as unknown as DurableObjectStorage;
  return { storage, close: () => database.close() };
}
