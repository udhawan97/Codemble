function normalize(value: string): string {
  return value.trim();
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
