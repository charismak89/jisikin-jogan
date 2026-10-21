import type { DayData } from '../types'
import { dir, nf, sg } from '../lib/fmt'
import { Card } from './ui/card'

function Chip({ label, v, sub }: { label: string; v: number | null; sub?: string | null }) {
  return (
    <span className="inline-flex items-baseline gap-1.5 rounded-full bg-card2 px-3 py-1.5 text-[13px]">
      <span className="text-tx3">{label}</span>
      <b className={`num ${dir(v)}`}>{v == null ? '미확보' : sg(v)}</b>
      {sub && <span className="text-[11px] text-tx3">{sub}</span>}
    </span>
  )
}

export function Hero({ data, onBrief }: { data: DayData; onBrief: () => void }) {
  const f = data.forecast, s = data.signals
  const hasBand = f.low != null && f.high != null && f.prev_close
  const center = f.low_pct != null && f.high_pct != null ? (f.low_pct + f.high_pct) / 2 : null   // 방향 3분류 대신 구간 중심(2026-10-21)
  return (
    <Card aria-label="시초가 전망" className="lg:p-8">
      <div className="text-[13px] font-semibold text-tx3">09:00 코스피 시초가 전망</div>
      <div className="mt-1 text-[26px] font-extrabold leading-tight tracking-tight text-tx sm:text-[30px]">{center != null ? `${sg(center)} 안팎 출발` : hasBand ? '구간 전망' : '전망 없음'}</div>
      {hasBand ? (
        <div className="num mt-1 text-[20px] font-bold text-brand sm:text-[22px]">
          {nf(f.low as number, 0)} ~ {nf(f.high as number, 0)}
          <small className="ml-2 text-[13px] font-semibold text-tx3">{sg(f.low_pct as number)} ~ {sg(f.high_pct as number)}</small>
        </div>
      ) : <div className="mt-1 text-[16px] text-tx3">구간 없음</div>}
      {hasBand && <Band data={data} />}
      <div className="mt-4 flex flex-wrap gap-2">
        <Chip label="야간선물" v={s.k200n_pct} sub={s.k200n_asof} />
        <Chip label="EWY 시사" v={s.ewy_implied_pct} />
        <Chip label="ADR 시사" v={s.adr_implied_pct} />
      </div>
      <ol className="mt-5 space-y-2.5 border-t border-line pt-4">
        {data.concl.map((c, i) => (
          <li key={i} className="flex gap-3 text-[15px] leading-snug text-tx">
            <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-brand-soft text-[12px] font-bold text-brand">{i + 1}</span>
            <span className="font-semibold">{c.h}</span>
          </li>
        ))}
      </ol>
      <button type="button" onClick={onBrief} className="mt-4 text-[13px] font-bold text-brand">근거와 시나리오는 브리핑에서 →</button>
    </Card>
  )
}

/** 전일 종가(0%)와 예상 구간을 한 줄에 */
function Band({ data }: { data: DayData }) {
  const f = data.forecast, lo = f.low_pct as number, hi = f.high_pct as number
  const min = Math.min(-1, lo - 0.5), max = Math.max(1, hi + 0.5), P = (v: number) => ((v - min) / (max - min)) * 100
  return (
    <div className="mt-4" aria-label={`예상 구간 ${sg(lo)} ~ ${sg(hi)}, 전일 종가 기준`}>
      <div className="relative h-3 rounded-full bg-card2">
        <div className="absolute top-0 h-3 rounded-full" style={{ left: `${P(lo)}%`, width: `${P(hi) - P(lo)}%`, background: 'var(--band)', boxShadow: 'inset 0 0 0 1px var(--band-line)' }} />
        <div className="absolute -top-1 h-5 w-0.5 bg-tx3" style={{ left: `${P(0)}%` }} />
      </div>
      <div className="relative mt-1 h-4 text-[11px] text-tx3">
        <span className="absolute -translate-x-1/2" style={{ left: `${P(0)}%` }}>전일 종가</span>
      </div>
    </div>
  )
}
