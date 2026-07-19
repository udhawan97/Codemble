export interface Box<T> {
  value: T;
}

function normalize(value: string): string {
  return value.trim();
}

export function box<T>(value: T): Box<T> {
  return { value };
}

export function display(value?: string): string {
  return value?.trim() ?? "missing";
}

export function helper(value: string): string {
  return normalize(value);
}

export class Formatter {
  format(value: string): string {
    return normalize(value);
  }

  wrap(value: string): string {
    return this.format(value);
  }
}
