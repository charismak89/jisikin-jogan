export type Pt = [number, number]            // [시각 ms, 전일 종가 대비 %]
export type Bar = [number, number, number]   // [표시 시각 ms, %, 봉 시작 ms]

export interface Ent {
  key: string; name: string; coin: string; unit: string; approx: boolean; tick: number; dec: number
  prev: number; prev_label: string; base: number | null; path: Pt[]
  lo: number | null; hi: number | null; lo_v: number | null; hi_v: number | null; night: number | null
}
export interface DayCfg {
  issue: string; api: string; relay: string | null
  t_prev: number; t_snap: number; t_open: number; t_close: number; t_night: number
  ent: Ent[]
}
export interface K20Row {
  date: string; today: boolean; close: number | null; low: number | null; high: number | null
  open: number | null; in_range: boolean | null; verdict: string | null
}
export interface DayData {
  schema: number; issue: string; issue_no: string; date_label: string
  forecast: { dir: string | null; low: number | null; high: number | null; prev_close: number | null; night: number | null; low_pct: number | null; high_pct: number | null }
  concl: { h: string; b: string }[]
  signals: { k200n_pct: number | null; k200n_asof: string | null; ewy_implied_pct: number | null; adr_implied_pct: number | null; es_pct: number | null; nq_pct: number | null; perp_asof: string | null }
  day: DayCfg
  k20: { rows: K20Row[]; close: number | null; pct: number | null; cap: string }
  market: { key: string; label: string; close: number | null; pct: number | null; asof: string | null }[]
  global_tag: string; stock_note: string; brief_html: string
  footer: { sources: string; data_note: string }
}
