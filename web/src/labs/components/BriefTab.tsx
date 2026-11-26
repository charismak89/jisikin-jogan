import { useEffect, useRef, useState } from 'react'
import type { DayData } from '../../types'
import briefCss from '../brief.css?inline'
import { Button } from './ui/button'

// 브리핑 본문은 render.py 가 template-v5.html 로 만든 HTML 그대로다(지난 회차 archive/ 와 글자까지 같다). 실험실은 표준 A 로 바꾼 labs/brief.css 로 입힌다.
// 다크는 몽타주 변수가 문서 :root(data-theme, 시스템 설정)에서 바뀌어 Shadow DOM 으로 상속되므로 따로 맞추지 않는다.
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
  }, [data])

  const toggle = () => {
    const next = !open
    root.current?.querySelectorAll('details').forEach((d) => { d.open = next })
    setOpen(next)
  }
  return (
    <div>
      <div className="mb-3 flex justify-end">
        <Button variant="assistive" size="small" onClick={toggle}>{open ? '전부 접기' : '전부 펼치기'}</Button>
      </div>
      <div ref={host} />
    </div>
  )
}
const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
