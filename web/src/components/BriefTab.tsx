import { useEffect, useRef, useState } from 'react'
import type { DayData } from '../types'
import { site } from '../lib/site'

// 브리핑 본문은 render.py 가 만든 v5 HTML 그대로다(글자까지 같다). 기존 style.css 가 새 화면과 부딪치지 않도록 Shadow DOM 안에서 그린다.
let cssP: Promise<string> | null = null
const loadCss = () => (cssP ||= fetch(site('style.css')).then((r) => (r.ok ? r.text() : '')).catch(() => ''))
// :root 선택자를 shadow host 로 옮긴다 (테마 속성 data-jj 는 host 에 단다)
const scope = (css: string) => css
  .replace(/:root:not\(\[data-jj\]\)/g, ':host(:not([data-jj]))')
  .replace(/:root\[data-jj="dark"\]/g, ':host([data-jj="dark"])')
  .replace(/:root\[data-jj="light"\]/g, ':host([data-jj="light"])')
  .replace(/:root\b/g, ':host')

export function BriefTab({ data }: { data: DayData }) {
  const host = useRef<HTMLDivElement>(null)
  const root = useRef<ShadowRoot | null>(null)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const el = host.current
    if (!el) return
    const sr = root.current || (root.current = el.attachShadow({ mode: 'open' }))
    let alive = true
    loadCss().then((css) => {
      if (!alive) return
      sr.innerHTML = `<style>${scope(css)} :host{display:block;font-family:inherit} .wrap{max-width:none;padding:0} body{background:transparent}</style>` +
        `<div class="wrap-6">${data.brief_html}<footer>${esc(data.footer.sources)}<br>${esc(data.footer.data_note)}<br>개인 학습용 기록입니다. 투자 자문이나 매매 권유가 아니며, 모든 판단과 책임은 열람자 본인에게 있습니다.</footer></div>`
    })
    const sync = () => el.setAttribute('data-jj', document.documentElement.getAttribute('data-jj') || 'light')
    sync()
    const mo = new MutationObserver(sync)
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ['data-jj'] })
    return () => { alive = false; mo.disconnect() }
  }, [data])

  const toggle = () => {
    const next = !open
    root.current?.querySelectorAll('details').forEach((d) => { d.open = next })
    setOpen(next)
  }
  return (
    <div>
      <div className="mb-3 flex justify-end">
        <button type="button" onClick={toggle} className="rounded-full border border-line bg-card px-3.5 py-1.5 text-[13px] font-semibold text-tx2">{open ? '전부 접기' : '전부 펼치기'}</button>
      </div>
      <div ref={host} className="rounded-3xl bg-card p-2 shadow-[var(--shadow)] sm:p-4" />
    </div>
  )
}
const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
