export type Level = "debug" | "info" | "warn" | "error";

const lines: string[] = [];

export function log(level: Level, message: string): void {
  lines.push(`${new Date().toISOString()} ${level.toUpperCase()} ${message}`);
}

export function recentLogs(): string[] {
  return lines.slice(-100);
}
