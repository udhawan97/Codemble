import { helper } from "./util";
import React from "react";

export class Widget {
  run(value: string): string {
    return helper(value);
  }
}

export const Card = ({ title }: { title: string }) => (
  <article>{title}</article>
);
