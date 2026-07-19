import { helper } from "./util.js";
import { Widget } from "./widget";

export async function main(input: string): Promise<string> {
  const value = await helper(input);
  return new Widget().run(value);
}

if (import.meta.main) {
  main("ready");
}
