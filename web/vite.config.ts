import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { readFileSync, renameSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
const here = (p: string) => fileURLToPath(new URL(p, import.meta.url))

// 2026-10-19 메인 전환: 저장소 루트 index.html 도 v6 앱이다. 산출물(assets)은 v6/ 한 곳에 두고,
// 루트 index.html 은 v6/index.html 의 자산 경로만 ./v6/assets/ 로 바꿔 쓴다. /v6/ 주소도 그대로 열린다.
const rootShell = (): Plugin => ({
  name: 'jogan-root-shell',
  closeBundle() {
    const html = readFileSync(here('../v6/index.html'), 'utf-8')
    const out = html.replace(/(src|href)="\.\/assets\//g, '$1="./v6/assets/')
    if (out === html) throw new Error('루트 index.html: 자산 경로(./assets/)를 찾지 못함')
    writeFileSync(here('../index.html'), out)
  },
})

// 실험실(2026-11-26, 처음 이름 stg): `vite build --mode labs` 는 web/labs.html 을 저장소 루트 labs/ 로 낸다.
// 주소는 /jisikin-jogan/labs/. 메인(v6/, 루트 index.html)은 건드리지 않는다. 다 보면 메인 진입점을 바꿔 전환한다
const labsIndex = (): Plugin => ({
  name: 'jogan-labs-index',
  closeBundle() { renameSync(here('../labs/labs.html'), here('../labs/index.html')) },
})

// 산출물은 저장소 루트의 v6/ 로 낸다. 루틴은 이 앱을 빌드하지 않는다 — UI 를 바꿀 때만 빌드해 커밋한다.
export default defineConfig(({ mode }) => mode === 'labs'
  ? {
      base: './',
      plugins: [react(), tailwindcss(), labsIndex()],
      build: { outDir: '../labs', emptyOutDir: true, sourcemap: false, rollupOptions: { input: here('labs.html') } },
    }
  : {
      base: './',
      plugins: [react(), tailwindcss(), rootShell()],
      build: { outDir: '../v6', emptyOutDir: true, sourcemap: false },
    })
