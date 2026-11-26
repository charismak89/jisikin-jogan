// 몽타주(@montage-ui/theme) 토큰을 CSS 변수로 옮긴다. 값은 손으로 적지 않는다.
//   node scripts/gen-tokens.mjs           src/styles/montage.css 를 다시 쓴다
//   node scripts/gen-tokens.mjs --check   파일이 패키지 값과 다르면 exit 1 (CI, build)
//   node scripts/gen-tokens.mjs --report  주요 글자 토큰의 대비를 표로 찍는다
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { lightOriginTheme as L, darkOriginTheme as D } from '@montage-ui/theme';

const OUT = fileURLToPath(new URL('../src/styles/montage.css', import.meta.url));
const A = L.atomic;

// 금융 화면 전용 토큰. 몽타주에는 등락 색이 없어 원자 색에서 고른다(국내 관례: 상승 빨강, 하락 파랑).
// 대비 4.5:1 이상이 나오는 단계로 골랐다(--report 로 확인).
const finance = {
  light: { up: A.red[40], down: A.blue[40], flat: L.semantic.foreground.neutral.secondary },
  dark: { up: A.red[60], down: A.blue[60], flat: D.semantic.foreground.neutral.secondary },
};

const kebab = (s) => s.replace(/([a-z0-9])([A-Z])/g, '$1-$2').toLowerCase();

function flatten(obj, prefix, out = []) {
  for (const [k, v] of Object.entries(obj)) {
    if (k === 'platform') continue; // iOS 전용 블록
    const name = `${prefix}-${kebab(String(k))}`;
    if (v && typeof v === 'object') flatten(v, name, out);
    else out.push([name, String(v)]);
  }
  return out;
}

function vars(semantic, fin) {
  const rows = flatten(semantic, '--mt');
  for (const [k, v] of Object.entries(fin)) rows.push([`--mt-fin-${k}`, v]);
  return rows.map(([k, v]) => `  ${k}: ${v};`).join('\n');
}

function scale() {
  const rows = [];
  for (const [k, v] of Object.entries(L.radius)) rows.push([`--mt-radius-${k}`, v]);
  for (const [k, v] of Object.entries(L.typography)) {
    const n = kebab(k);
    rows.push([`--mt-type-${n}-size`, v.fontSize], [`--mt-type-${n}-line`, v.lineHeight], [`--mt-type-${n}-track`, v.letterSpacing]);
  }
  return rows.map(([k, v]) => `  ${k}: ${v};`).join('\n');
}

const version = JSON.parse(readFileSync(new URL('../node_modules/@montage-ui/theme/package.json', import.meta.url))).version;
const css = `/* 자동 생성: scripts/gen-tokens.mjs, @montage-ui/theme ${version}. 손으로 고치지 않는다. */
:root {
${scale()}
${vars(L.semantic, finance.light)}
}
:root[data-theme='dark'] {
${vars(D.semantic, finance.dark)}
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme='light']) {
${vars(D.semantic, finance.dark).replace(/^/gm, '  ')}
  }
}
`;

const arg = process.argv[2];
if (arg === '--check') {
  let cur = '';
  try { cur = readFileSync(OUT, 'utf8'); } catch {}
  if (cur !== css) {
    console.error('montage.css 가 @montage-ui/theme 값과 다르다. npm run tokens 로 다시 만든다.');
    process.exit(1);
  }
  console.log(`montage.css 일치 (@montage-ui/theme ${version})`);
} else if (arg === '--report') {
  const hex = (h) => { const s = h.replace('#', ''); return [0, 2, 4, 6].map((i) => (i < s.length ? parseInt(s.slice(i, i + 2), 16) : 255)); };
  const over = (fg, bg) => { const a = fg[3] / 255; return [0, 1, 2].map((i) => fg[i] * a + bg[i] * (1 - a)); };
  const lum = (c) => { const [r, g, b] = c.map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const ratio = (fg, bg) => { const b = hex(bg).slice(0, 3); const f = over(hex(fg), b); const [x, y] = [lum(f), lum(b)].sort((p, q) => q - p); return ((x + 0.05) / (y + 0.05)).toFixed(2); };
  for (const [mode, T, F] of [['light', L, finance.light], ['dark', D, finance.dark]]) {
    const bg = T.semantic.background.neutral.primary;
    const fg = T.semantic.foreground;
    const rows = { 'neutral.primary': fg.neutral.primary, 'neutral.secondary': fg.neutral.secondary, 'neutral.tertiary': fg.neutral.tertiary, 'brand.primary': fg.brand.primary, 'positive.primary': fg.positive.primary, 'negative.primary': fg.negative.primary, 'fin.up': F.up, 'fin.down': F.down };
    console.log(`\n${mode} (바탕 ${bg})`);
    for (const [k, v] of Object.entries(rows)) console.log(`  ${k.padEnd(18)} ${v.padEnd(10)} ${ratio(v, bg)}:1`);
    const s = T.semantic.surface;
    const subtle = '#' + over(hex(s.brand.subtle), hex(bg).slice(0, 3)).map((x) => Math.round(x).toString(16).padStart(2, '0')).join('');
    console.log(`  ${'on-brand(단추)'.padEnd(18)} ${T.semantic.static.white.padEnd(10)} ${ratio(T.semantic.static.white, s.brand.primary)}:1 (바탕 ${s.brand.primary})`);
    console.log(`  ${'brand-fg(배지)'.padEnd(18)} ${fg.brand.primary.padEnd(10)} ${ratio(fg.brand.primary, subtle)}:1 (바탕 brand-subtle)`);
  }
} else {
  writeFileSync(OUT, css);
  console.log(`montage.css 생성 (@montage-ui/theme ${version})`);
}
