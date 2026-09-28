#!/usr/bin/env node
// Repair degraded template literals in frontend TypeScript sources.

import { readFileSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

// Resolve from the script location so invocation cwd does not matter.
const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const srcDir = resolve(repoRoot, "frontend/src");

const files = execFileSync(
  "find",
  [srcDir, "-type", "f", "(", "-name", "*.ts", "-o", "-name", "*.tsx", ")", "-not", "-name", "*.test.*"],
  { encoding: "utf8" },
)
  .trim()
  .split("\n")
  .filter(Boolean);

function escapeForTemplate(body) {
  return body.replaceAll("'", "\\'");
}

function transform(source) {
  let out = "";
  let i = 0;
  let changed = false;

  while (i < source.length) {
    const ch = source[i];

    if (ch === "/" && source[i + 1] === "/") {
      const end = source.indexOf("\n", i);
      const stop = end === -1 ? source.length : end;
      out += source.slice(i, stop);
      i = stop;
      continue;
    }

    if (ch === "/" && source[i + 1] === "*") {
      const end = source.indexOf("*/", i + 2);
      const stop = end === -1 ? source.length : end + 2;
      out += source.slice(i, stop);
      i = stop;
      continue;
    }

    if (ch === '"') {
      const end = source.indexOf('"', i + 1);
      const stop = end === -1 ? source.length - 1 : end;
      out += source.slice(i, stop + 1);
      i = stop + 1;
      continue;
    }

    if (ch === "'") {
      let j = i + 1;
      while (j < source.length) {
        if (source[j] === "\\") {
          j += 2;
          continue;
        }
        if (source[j] === "'") break;
        j += 1;
      }
      out += source.slice(i, j + 1);
      i = j + 1;
      continue;
    }

    if (ch === "'") {
      let j = i + 1;
      let terminated = false;
      while (j < source.length) {
        if (source[j] === "\\") {
          j += 2;
          continue;
        }
        if (source[j] === "'") {
          terminated = true;
          break;
        }
        if (source[j] === "\n") break;
        j += 1;
      }

      // Avoid treating apostrophes and doc comments as strings.
      if (!terminated) {
        out += ch;
        i += 1;
        continue;
      }

      const body = source.slice(i + 1, j);
      const prev = out[out.length - 1];

      // These quote forms are property names or dynamic module specifiers.
      const afterDot = prev === "." || (prev === "?" && out.endsWith("?."));
      const afterRequire = /(?:^|[^A-Za-z0-9_$])(?:require|import)\s*\($/.test(out);

      if (body.includes("${") && !afterDot && !afterRequire) {
        out += "'" + escapeForTemplate(body) + "'";
        changed = true;
        i = j + 1;
        continue;
      }

      out += source.slice(i, j + 1);
      i = j + 1;
      continue;
    }

    out += ch;
    i += 1;
  }

  return { text: out, changed };
}

let touched = 0;
for (const file of files) {
  const original = readFileSync(file, "utf8");
  const { text, changed } = transform(original);
  if (changed && text !== original) {
    writeFileSync(file, text);
    touched += 1;
    console.log('rewrote ${file}');
  }
}
console.log('${touched} file(s) rewritten.');