import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// 산출물은 저장소 루트의 v6/ 로 낸다(GitHub Pages 가 /v6/ 로 서빙). 루틴은 이 앱을 빌드하지 않는다 — UI 를 바꿀 때만 빌드해 커밋한다.
export default defineConfig({
  base: './',
  plugins: [react(), tailwindcss()],
  build: { outDir: '../v6', emptyOutDir: true, sourcemap: false },
})
