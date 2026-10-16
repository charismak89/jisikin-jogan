import type { DayData } from '../types'
import { arrow, dir, nf, sg } from '../lib/fmt'
import { Card, CardHead } from './ui/card'

export function Market({ data }: { data: DayData }) {
  return (
    <Card aria-label="간밤 시장">
      <CardHead title="간밤 시장" right={data.global_tag} />
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {data.market.map((m) => (
          <div key={m.key} className="rounded-2xl bg-card2 p-3">
            <div className="text-[12px] font-semibold text-tx2">{m.label}{m.asof && <small className="ml-1 text-tx3">{m.asof}</small>}</div>
            <div className="num mt-0.5 text-[17px] font-bold text-tx">{m.close != null ? nf(m.close, m.key === 'USDKRW' ? 2 : 2) : '—'}</div>
            <div className={`num text-[12px] font-semibold ${dir(m.close != null ? m.pct : null)}`}>{m.close != null && m.pct != null ? arrow(m.pct) + sg(m.pct) : '미확보'}</div>
          </div>
        ))}
      </div>
    </Card>
  )
}
