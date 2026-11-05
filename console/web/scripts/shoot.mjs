// Design QA: screenshots the Console's design mode (?scene=&theme=&bp=) at every scene × theme × breakpoint and
// pixel-diffs each against the renders in docs/design/renders/ (ground truth; the render set is kept out of git).
//   node scripts/shoot.mjs [filter]      (Console server on http://127.0.0.1:7300; writes docs/screenshots/design/)
// 1920 frames are also compared with docs/design/renders/local/ when present: the same kit sources re-rendered on this
// machine (node batch.js <dir> console-). The handoff PNGs were rendered elsewhere; kit-vs-kit differs by ~0.3–0.46 %.
import fs from 'node:fs'; import path from 'node:path'; import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright'; import pixelmatch from 'pixelmatch'; import { PNG } from 'pngjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const RENDERS = path.join(ROOT, 'docs/design/renders');
const OUT = path.join(ROOT, 'docs/screenshots/design');
const BASE = process.env.CONSOLE_URL ?? 'http://127.0.0.1:7300';
const SCENES = { hero: 'live', 'a-refusal': 'refusal', 'b-bytediff': 'bytediff', 'c-viewas-payco': 'payco', 'd1-ledger': 'ledger',
  'd2-guard': 'guard', 'e-finale': 'finale', loading: 'loading', empty: 'empty', replay: 'replay', present: 'present' };
const BPS = { w1920: [1920, 1080], w1440: [1440, 900], w1280: [1280, 800], tablet: [834, 1194] };
const KIT_FONTS = path.join(RENDERS, 'standalone-kit/site/fonts');
// Same fonts as the kit's batch.js: Google Fonts requests are answered with the kit's local Geist files.
const FONT_CSS = `@font-face{font-family:'Geist';src:url(https://cw-fonts.invalid/Geist-Variable.woff2) format('woff2');font-weight:100 900;font-style:normal;font-display:block}
@font-face{font-family:'Geist Mono';src:url(https://cw-fonts.invalid/GeistMono-Variable.woff2) format('woff2');font-weight:100 900;font-style:normal;font-display:block}`;
async function routeFonts(page) {
  await page.route(/fonts\.(googleapis|gstatic)\.com/, (r) => r.fulfill({ status: 200, contentType: 'text/css', body: FONT_CSS }));
  await page.route(/cw-fonts\.invalid\//, (r) => r.fulfill({ status: 200, contentType: 'font/woff2', body: fs.readFileSync(path.join(KIT_FONTS, path.basename(new URL(r.request().url()).pathname))) }));
}
const localRef = (s, t, bp) => (bp === 'w1920' ? path.join(RENDERS, 'local', `console-${s}-${t}.png`) : null);
const compare = (file, ref, H, out) => {
  const a = PNG.sync.read(fs.readFileSync(file)), b = PNG.sync.read(fs.readFileSync(ref));
  if (a.width !== b.width || a.height !== b.height) return null;
  const rows4 = (p) => p.data.subarray(0, a.width * H * 4);
  const diff = out ? new PNG({ width: a.width, height: H }) : null;
  const n = pixelmatch(rows4(a), rows4(b), diff?.data ?? null, a.width, H, { threshold: 0.1 });
  const pct = (100 * n) / (a.width * H);
  if (out && pct > 0.5) fs.writeFileSync(out, PNG.sync.write(diff));
  return pct;
};
const reference = (s, t, bp) => bp === 'w1920' ? path.join(RENDERS, `console-${s}-${t}.png`) : path.join(RENDERS, 'responsive', `console-${s}-${t}-${bp}.png`);

const filter = process.argv[2];
if (!filter) fs.rmSync(path.join(OUT, 'diff'), { recursive: true, force: true });   // full run: no stale diff images
fs.mkdirSync(path.join(OUT, 'diff'), { recursive: true });
const browser = await chromium.launch();
const rows = [];
for (const [s, scene] of Object.entries(SCENES)) for (const theme of ['dark', 'light']) for (const [bp, [w, h]] of Object.entries(BPS)) {
  const name = `console-${s}-${theme}-${bp}`;
  if (filter && !name.includes(filter)) continue;
  const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
  await routeFonts(page);
  await page.goto(`${BASE}/?scene=${scene}&theme=${theme}&bp=${bp}`, { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(3200);                       // same settle time as the kit's batch.js
  const file = path.join(OUT, `${name}.png`);
  await page.screenshot({ path: file });
  await page.close();
  const ref = reference(s, theme, bp);
  if (!fs.existsSync(ref)) { rows.push([name, 'no reference', '']); continue; }
  // Presentation mode is always a 1920×1080 frame; below it (tablet viewport) the kit page is unstyled white,
  // so only the frame area is compared there (an intentional difference).
  const H = scene === 'present' ? Math.min(h, 1080) : h;
  const pct = compare(file, ref, H, path.join(OUT, 'diff', `${name}.png`));
  if (pct === null) { rows.push([name, 'size mismatch', '']); continue; }
  const lr = localRef(s, theme, bp);
  const local = lr && fs.existsSync(lr) ? compare(file, lr, H, null) : null;
  const ok = pct <= 0.5 || (local !== null && local <= 0.5);
  rows.push([name, `${pct.toFixed(2)}%`, ok ? 'match' : 'DIFF', local === null ? '' : `local kit ${local.toFixed(2)}%`]);
  console.log(name, `${pct.toFixed(2)}%`, local === null ? '' : `(local kit ${local.toFixed(2)}%)`);
}
await browser.close();
fs.writeFileSync(path.join(OUT, 'report.json'), JSON.stringify(rows, null, 1));
const bad = rows.filter((r) => r[2] !== 'match');
console.log(`\n${rows.length - bad.length}/${rows.length} within 0.5% (of the handoff render, or of the same kit source re-rendered here)`); for (const r of bad) console.log('  ', r.join('  '));
