import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import '../index.css'

// 시험 화면(/stg/) 진입점. 메인(v6)과 같은 day.json·중계기·추종가를 쓰고, 화면만 따로 고친다(2026-11-26)
createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>)
