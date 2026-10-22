import { useState } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import type { Live } from '../lib/live'

// 글은 중계기 VM 에만 저장된다(저장소에는 올리지 않는다). 2026-10-19 부터 키 없이도 보낸다(중계기 PUBLIC_VIEW). 키가 있으면 같이 보낸다.
const CATS = ['제안', '오류', '예측', '기타']

export function Feedback({ live, tab }: { live: Live; tab: string }) {
  const [open, setOpen] = useState(false)
  const [cat, setCat] = useState(CATS[0])
  const [text, setText] = useState('')
  const [nick, setNick] = useState(() => { try { return localStorage.getItem('jj-nick') || '' } catch { return '' } })
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)

  const send = (ev: React.FormEvent) => {
    ev.preventDefault()
    const t = text.trim()
    if (!t) return
    try { localStorage.setItem('jj-nick', nick.trim()) } catch { /* 저장 불가 */ }
    setBusy(true); setMsg('보내는 중…')
    fetch(live.D.relay + '/v1/feedback' + (live.RK ? '?k=' + encodeURIComponent(live.RK) : ''), {
      method: 'POST', headers: { 'Content-Type': 'text/plain;charset=UTF-8' },   // text/plain — 사전 요청 없이 보낸다
      body: JSON.stringify({ cat, text: t, nick: nick.trim(), ctx: { issue: live.D.issue, tab: tab === 'brief' ? 'brief' : 'dash', mode: live.krxOK === false ? 'krx-fail' : 'krx', w: String(window.innerWidth), page: location.pathname } }),
    }).then((r) => {
      if (r.ok) { setText(''); setMsg('받았습니다. 토요일 점검 때 읽겠습니다.'); setTimeout(() => setOpen(false), 1600); return }
      setMsg(r.status === 429 ? '지금은 더 보낼 수 없어요. 잠시 뒤나 내일 다시 보내 주세요.' : `보내지 못했어요 (오류 ${r.status}). 잠시 뒤 다시 시도해 주세요.`)
    }, () => setMsg('보내지 못했어요. 연결을 확인하고 다시 시도해 주세요.')).then(() => setBusy(false))
  }

  return (
    <Dialog.Root open={open} onOpenChange={(o) => { setOpen(o); if (o) setMsg('') }}>
      <Dialog.Trigger className="rounded-full border border-line bg-card px-3.5 py-1.5 text-[13px] font-bold text-tx2">의견</Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40" />
        {/* 모바일은 아래에서 올라오는 창, 태블릿·PC 는 가운데 창. 화면이 넓을수록 창과 입력 칸도 커진다(2026-10-22) */}
        <Dialog.Content className="fixed inset-x-4 bottom-4 z-50 mx-auto max-w-md rounded-3xl bg-card p-5 shadow-xl sm:bottom-auto sm:top-1/2 sm:max-w-xl sm:-translate-y-1/2 sm:p-6 lg:max-w-2xl lg:p-8 xl:max-w-3xl">
          <form onSubmit={send}>
            <Dialog.Title className="text-[17px] font-bold text-tx lg:text-[20px]">의견 보내기</Dialog.Title>
            <Dialog.Description className="mt-1 text-[13px] leading-relaxed text-tx3 lg:text-[14px]">틀린 값, 보고 싶은 것, 예측이 맞았는지 무엇이든 적어 주세요. 운영자와 Claude가 읽고 매주 토요일 개선 계획에 반영합니다.</Dialog.Description>
            <div role="radiogroup" aria-label="분류" className="mt-3 flex gap-2">
              {CATS.map((c) => (
                <button key={c} type="button" role="radio" aria-checked={cat === c} onClick={() => setCat(c)}
                  className={`rounded-full px-3 py-1.5 text-[13px] font-semibold ${cat === c ? 'bg-brand text-white' : 'bg-card2 text-tx2'}`}>{c}</button>
              ))}
            </div>
            <textarea value={text} onChange={(e) => setText(e.target.value)} maxLength={1000} rows={4} autoFocus
              placeholder="예) 하이닉스 시가가 증권 앱과 달라요 / 코스닥도 보고 싶어요"
              className="mt-3 w-full resize-none rounded-2xl border border-line bg-card2 p-3 text-[14px] text-tx placeholder:text-tx3 sm:min-h-40 sm:resize-y lg:min-h-56 lg:p-4 lg:text-[15px]" />
            <div className="mt-3 flex gap-2">
              <input value={nick} onChange={(e) => setNick(e.target.value)} maxLength={20} placeholder="닉네임 (선택)" autoComplete="nickname"
                className="min-w-0 flex-1 rounded-2xl border border-line bg-card2 px-3 text-[14px] text-tx placeholder:text-tx3" />
              <Dialog.Close type="button" className="rounded-2xl px-4 py-2.5 text-[14px] font-semibold text-tx2">닫기</Dialog.Close>
              <button type="submit" disabled={busy} className="rounded-2xl bg-brand px-5 py-2.5 text-[14px] font-bold text-white disabled:opacity-50">보내기</button>
            </div>
            <p role="status" aria-live="polite" className="mt-2 min-h-5 text-[13px] text-tx2">{msg}</p>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
