export type Pt = [number, number]            // [시각 ms, 전일 종가 대비 %]
export type Bar = [number, number, number]   // [표시 시각 ms, %, 봉 시작 ms]
export type Ohlc = [number, number, number, number, number]   // [봉 끝 ms, 시, 고, 저, 종 %] — 캔들(2026-11-27, 실험실)
export type DayOhlc = [string, number, number, number, number]   // [YYYY-MM-DD, 시, 고, 저, 종] — 코스피 일봉(중계기 /v1/kospi-daily, 2026-11-27 실험실)

export interface Ent {
  key: string; name: string; coin: string; unit: string; approx: boolean; tick: number; dec: number
  prev: number; prev_label: string; base: number | null; path: Pt[]
  lo: number | null; hi: number | null; lo_v: number | null; hi_v: number | null; night: number | null
}
export interface DayCfg {
  issue: string; api: string; relay: string | null
  t_prev: number; t_snap: number; t_open: number; t_close: number; t_night: number
  ent: Ent[]
  // 그날 정규장 시각(HH:MM). 수능일은 10:00~16:30. 2026-11-19 전 회차에는 없다 — 09:00~15:30 으로 본다
  sess?: { open: string; close: string; prev_close: string; why: string | null }
}
export interface K20Row {
  date: string; today: boolean; close: number | null; low: number | null; high: number | null
  open: number | null; in_range: boolean | null; verdict: string | null
}
export interface DayData {
  schema: number; issue: string; issue_no: string; date_label: string
  forecast: { low: number | null; high: number | null; prev_close: number | null; night: number | null; low_pct: number | null; high_pct: number | null }
  concl: { h: string; b: string }[]
  signals: { k200n_pct: number | null; k200n_asof: string | null; ewy_implied_pct: number | null; adr_implied_pct: number | null; es_pct: number | null; nq_pct: number | null; perp_asof: string | null }
  day: DayCfg
  k20: { rows: K20Row[]; close: number | null; pct: number | null; cap: string }
  market: { key: string; label: string; close: number | null; pct: number | null; asof: string | null }[]
  issue_src?: { t: string; origin: string; at: string | null; verify: string | null }[]   // 이슈 출처(B6). 2026-10-31 전 회차에는 없다
  // 06:00 뒤 코스피200 또는 종목(삼전, 하닉) 추종가가 1% 넘게 움직인 날 경고 줄(월요일 확장일 제외). 2026-11-18 전 회차와 조건이 아닌 날은 없거나 null
  post_note?: {
    text: string
    kospi: { post_pct: number; implied_pct: number; side: string; night_at: string; asof: string; text: string } | null
    stocks: { code: string; name: string; post_pct: number }[]
  } | null
  global_tag: string; stock_note: string; brief_html: string
  footer: { sources: string; data_note: string }
}
