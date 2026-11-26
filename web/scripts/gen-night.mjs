// 실험실 첫 카드의 밤 하늘(data-sky="night")에 몽타주 다크 값을 그 카드 안에서만 덮는다.
// 몽타주 생성 파일(montage.css)은 다크 값을 :root 에만 걸어서, 라이트 테마에서도 남색이 되는 밤 카드에 쓸 수 없다.
// 값은 손으로 적지 않고 gen-tokens.mjs 와 같은 패키지, 같은 규칙으로 만든다(gen-tokens.mjs 는 모의투자 봇 원본 그대로 둔다).
//   node scripts/gen-night.mjs           src/labs/montage-night.css 를 다시 쓴다
//   node scripts/gen-night.mjs --check   파일이 패키지 값과 다르면 exit 1 (build)
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { lightOriginTheme as L, darkOriginTheme as D } from '@montage-ui/theme';

const OUT = fileURLToPath(new URL('../src/labs/montage-night.css', import.meta.url));
// gen-tokens.mjs 의 finance.dark 와 같은 규칙(원자 색 red 60, blue 60, 다크 neutral.secondary)
const fin = { up: L.atomic.red[60], down: L.atomic.blue[60], flat: D.semantic.foreground.neutral.secondary };

const kebab = (s) => s.replace(/([a-z0-9])([A-Z])/g, '$1-$2').toLowerCase();
function flatten(obj, prefix, out = []) {
  for (const [k, v] of Object.entries(obj)) {
    if (k === 'platform') continue;
    const name = `${prefix}-${kebab(String(k))}`;
    if (v && typeof v === 'object') flatten(v, name, out);
    else out.push([name, String(v)]);
  }
  return out;
}
const rows = flatten(D.semantic, '--mt');
for (const [k, v] of Object.entries(fin)) rows.push([`--mt-fin-${k}`, v]);
const version = JSON.parse(readFileSync(new URL('../node_modules/@montage-ui/theme/package.json', import.meta.url))).version;
const css = `/* 자동 생성: scripts/gen-night.mjs, @montage-ui/theme ${version}. 손으로 고치지 않는다. */
[data-sky='night'] {
${rows.map(([k, v]) => `  ${k}: ${v};`).join('\n')}
}
`;
if (process.argv[2] === '--check') {
  let cur = '';
  try { cur = readFileSync(OUT, 'utf8'); } catch {}
  if (cur !== css) { console.error('montage-night.css 가 @montage-ui/theme 값과 다르다. npm run tokens 로 다시 만든다.'); process.exit(1); }
  console.log(`montage-night.css 일치 (@montage-ui/theme ${version})`);
} else {
  writeFileSync(OUT, css);
  console.log(`montage-night.css 생성 (@montage-ui/theme ${version})`);
}
