// Patch next-themes 0.4.x so its FOUC-prevention <script> is rendered only on
// the server. React 19 + Next 16.2+ logs an ERROR ("Encountered a script tag
// while rendering React component") for client-rendered <script> elements,
// which aborts hydration of downstream Radix components and breaks click
// handlers (e.g. the language toggle popover).
//
// Mirrors shadcn-ui/ui PR #10238: guard the memoized ThemeScript component
// with `if (typeof window !== "undefined") return null;` so the script element
// is only emitted during SSR. Idempotent and tolerant of file absence so it is
// safe to run from the postinstall hook.

import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');
const targets = [
  resolve(root, 'node_modules/next-themes/dist/index.mjs'),
  resolve(root, 'node_modules/next-themes/dist/index.js'),
];

const MARKER = 'if(typeof window!=="undefined")return null;';
// Matches both `t.memo(({...,scriptProps:X})=>{` (mjs) and the equivalent
// pattern in the CJS bundle. The captured `varName` is used to know which
// bundle we are touching for logging only.
const PATTERN = /(t\.memo\(\(\{[^}]*scriptProps:[a-zA-Z]\}\)=>\{)/;

let touched = 0;
for (const file of targets) {
  if (!existsSync(file)) continue;
  const src = readFileSync(file, 'utf8');
  if (src.includes(MARKER)) continue; // already patched
  if (!PATTERN.test(src)) {
    console.warn(`[patch-next-themes] unexpected layout, skipping ${file}`);
    continue;
  }
  const patched = src.replace(PATTERN, `$1${MARKER}`);
  writeFileSync(file, patched);
  touched++;
  console.log(`[patch-next-themes] patched ${file}`);
}

if (touched === 0) console.log('[patch-next-themes] nothing to do');
