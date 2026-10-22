import { useEffect, useRef, useState } from 'react'
import type { DayData } from '../types'
import briefCss from '../brief.css?inline'

// 브리핑 본문은 render.py 가 template-v5.html 로 만든 HTML 그대로다(지난 회차 archive/ 와 글자까지 같다). 모양은 대시보드와 같은 토스풍 brief.css 로 입힌다(2026-10-22).
// Tailwind 유틸리티와 본문 클래스 이름(.num .up .grid 등)이 부딪치지 않도록 Shadow DOM 안에서 그린다. archive/ 는 그대로 style.css 를 쓴다.
export function BriefTab({ data }: { data: DayData }) {
  const host = useRef<HTMLDivElement>(null)
  const root = useRef<ShadowRoot | null>(null)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const el = host.current
    if (!el) return
    const sr = root.current || (root.current = el.attachShadow({ mode: 'open' }))
    sr.innerHTML = `<style>${briefCss}</style>` +
      `${data.brief_html}<footer>${esc(data.footer.sources)}<br>${esc(data.footer.data_note)}<br>개인 학습용 기록입니다. 투자 자문이나 매매 권유가 아니며, 모든 판단과 책임은 열람자 본인에게 있습니다.</footer>`
    const sync = () => el.setAttribute('data-jj', document.documentElement.getAttribute('data-jj') || 'light')
    sync()
    const mo = new MutationObserver(sync)
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ['data-jj'] })
    return () => mo.disconnect()
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
      <div ref={host} />
    </div>
  )
}
const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
