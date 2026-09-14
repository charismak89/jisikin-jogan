# RUNBOOK — 지식인 조간 회차 절차 (v2 · 2026-09-15 부터)

평일 07:45 KST, 개장 75분 전 반도체·메모리 브리핑. 결과물은 `render.py` 가 만드는 `out/index.html` · `out/calibration.json` · `out/state.json` 세 개.
확인 질문을 받아줄 사람이 없다. 애매하면 가정을 명시하고 진행한다. 이 파일이 예약작업 프롬프트보다 우선한다.

발행을 중단하는 경우는 둘뿐이다. (1) 휴장일 (2) `template-v4.html` 이 없을 때. 그 밖에 어떤 데이터가 없어도 없다고 밝히고 발행한다.

## 토큰 규칙 (이 작업의 제약 조건)
1. `template-v4.html` · `calibration.json` · `archive/` 를 열지 않는다. 스크립트가 처리한다. 읽는 파일은 `CONTEXT.md` 와 `state.json` 둘뿐이다.
2. `index.html` 을 직접 쓰지 않는다. 값과 문장만 `fill.json` 에 쓴다. HTML 태그·화살표·색·등락률·시사 갭·채점 문구는 `render.py` 가 만든다.
3. 시세 WebFetch 는 **한 턴에 병렬로** 부른다. 같은 URL 을 두 번 부르지 않는다. 프롬프트는 값만 짧게.
4. 스크린샷을 찍지 않는다. 레이아웃 검증은 `page.evaluate` 숫자만.

## 0. 휴장일
`python3 render.py --today` 가 `HOLIDAY` 를 내면 "휴장일 — 발행 생략" 한 줄만 남기고 종료한다.

## 1. 준비
저장소는 `repo/` 에 clone 돼 있다(부트스트랩 프롬프트가 한다). 없으면 `git clone --depth 1 https://github.com/charismak89/jisikin-jogan.git repo`. clone 이 안 되면 `https://raw.githubusercontent.com/charismak89/jisikin-jogan/main/<파일>` 로 `template-v4.html render.py score.py publish.py holidays.json CONTEXT.md state.json calibration.json` 을 curl 로 받는다.
모든 작업은 `repo/` 안에서 한다. `CONTEXT.md` 를 읽는다 — 종목 사실관계·표기명·소스 우선순위·이슈 수집 범위·금지 표현이 거기 있다. `state.json` 을 읽는다 — 직전 회차 전망(`forecast`)과 직전 영업일 종가(`closes`)가 있다. 둘 중 하나를 못 받아도 발행한다.

## 2. 시세 — 병렬 3턴
**턴 A · Google Finance 12개를 한 턴에 병렬로.** 프롬프트: "현재가, Previous close, Open, Day range, 시점 표기(GMT+9)만 값으로. 설명 없이."
`KOSPI:KRX` `005930:KRX` `000660:KRX` `402340:KRX` `009150:KRX` `0167A0:KRX` `442580:KRX` `NVDA:NASDAQ` `MU:NASDAQ` `EWY:NYSEARCA` `SKHY:NASDAQ` `USD-KRW` (`https://www.google.com/finance/quote/…`)
KOSPI 의 **Open** 은 직전 영업일 시초가다. 채점에 쓰므로 반드시 챙기고, 그 세션 날짜를 `open_date` 에 적는다. `state.forecast.date` 와 다르면(회차를 건너뛴 날) 그 날짜의 시가를 마감시황 기사에서 찾아 `score.actual_open`·`score.actual_open_date` 에 넣는다. 못 찾으면 채점 불가로 두고 억지로 채점하지 않는다.

**턴 B · 대조와 보완, 한 턴에 병렬로.**
- 한국경제 `https://markets.hankyung.com/stock/<코드>` 국내 6종 + 코스피 — `2026.09.11 장마감` 처럼 상태와 기준일이 찍힌다. `장중` 이면 종가가 아니다.
- **야간선물** `https://sonmul.co.kr/` — 야간 종가·등락률·기준시각·주간선물 종가. 월요일 값은 금요일 밤 세션이다(일요일 밤 세션은 없다).
- 주간 선물 `https://markets.hankyung.com/indices/kospi-future` (기준일 확인) · SOX `https://kr.investing.com/indices/phlx-semiconductor`
- WebSearch 1회: 직전 영업일 마감시황 기사 → 외국인·기관·개인 순매수, 코스닥 종가, 원달러 서울 종가

**턴 C · 빠진 것만 보충.** 없으면 생략한다.

판정 규칙
- 국내 종목·ETF·지수는 Google Finance 시각이 **15:30 대**여야 종가다. 09:00~15:20 이면 장중값이라 쓰지 않는다.
- 두 소스가 일치하면 확정. 어긋나면 기준일이 명시된 쪽을 채택하고 `data_note.more` 에 두 값과 채택 근거를 쓴다. 한 소스뿐이면 그렇게 밝힌다.
- 끝내 못 찾으면 `close: null`. **추정값 금지.** 몇 종목이 비어도 발행한다.
- 등락률은 `render.py` 가 `state.closes` 로 계산한다. 회차는 화면 등락률을 `pct_screen` 에 적기만 한다. 둘이 0.05%p 이상 다르면 render.py 가 경고하니 다시 확인하고 `data_note` 에 남긴다. −50% 같은 값이 나오면 액면분할을 의심하고 검색한다.
- EWY·ADR 시사 갭은 render.py 가 환율까지 넣어 계산한다. 회차가 계산하지 않는다.
- ADR(SKHY)은 나스닥 정규 상장이다. 유동성을 이유로 신호를 깎지 않는다. ADR 과 EWY 가 반대면 거래대금이 큰 EWY 를 우선한다.

## 3. 이슈
`CONTEXT.md` 의 "이슈 수집 범위" 를 그대로 따른다 — A 메모리 직접 재료 · B AI 내러티브(캐펙스·규제·CEO 발언과 **누가 동조했는가**) · C 매크로. 조회 창과 검색 상한도 거기 있다. 화~금은 검색 4회·본문 4건, 월요일과 연휴 뒤는 검색 6회·본문 5건. 가장 최근 재료가 몇 시 것인지 `sums.issue` 에 밝힌다.

## 4. 전망
- `calibration.json` 의 `rule.center_signal` 이 비어 있는 동안(지금)은 **기존 방식대로 사람처럼 판단**해 `forecast.dir/low/high` 를 정한다. 야간선물·EWY 시사·ADR 시사는 기록·표시만 하고 전망을 기계적으로 맞추지 않는다. 다만 야간선물과 반대 방향을 내면 `why` 에 이유를 한 문단 쓴다.
- `score.py` 가 "규칙 적용 — …" 줄을 내면(사람이 금요일에 켠 뒤) 그 구간을 그대로 `forecast` 에 쓴다.
- 방향 어휘는 `갭상승` / `보합` / `갭하락`. 채점은 |갭| 0.5% 기준이다 — 보합은 실제 갭이 ±0.5% 안일 때만 맞는다. 최근 17회차 중 ±0.5% 안은 5회뿐이니 보합은 신호가 정말 약할 때만 쓴다.
- 월요일·연휴 뒤 첫 회차: 주말 뉴스는 어떤 가격에도 들어 있지 않다. 구간을 평소보다 넓게 잡고, 주말 재료를 `checks.scenario`(가장 약한 고리)와 `bear`/`bull` 에 반드시 넣는다.
- 구간 근거는 최근 며칠 **실제 장중 고가·저가**에서 뽑는다. 실제 거래값인지 라운드 넘버인지 구분해 적는다.

## 5. 문체
- 평서형 존댓말("~습니다"). 개조식·명사형 종결 금지. 태그([사실] 등) 금지.
- 한 문장에 절 두 개까지. 영어를 옮긴 듯한 문장, 국가·시장을 사람처럼 부리는 주어 금지.
- 숫자에는 뜻을 붙인다. 예: "환율이 내렸다는 건 원화가 강해졌다는 뜻입니다."
- 낙관·비관 어느 쪽으로도 기울지 않는다. 자본정책 재료와 실적 재료를 구분한다. 매수·매도·비중 같은 실행 지시는 쓰지 않는다.
- ADR / SOX / HBM / DRAM / ETF / WTI 는 약어 그대로. 금지 표현과 쓸 어휘는 `CONTEXT.md` 표를 따른다(render.py 가 grep 한다).
- 독자는 출근길 스마트폰으로 5분 안에 읽는다. **접힘 상태 4,000자 초과는 실패한 회차다.** 길게 쓸 내용은 `more` 배열(접기)로 보낸다.

## 6. fill.json — 값과 문장만. HTML 금지. 리스트는 스키마가 배열인 곳에만
글자 상한은 접힘 상태에서 보이는 부분 기준(공백 포함). `more` 는 `<p>` 하나가 배열 원소 하나.
```
{"issue_date":"2026-09-15", "closes_as_of":"2026-09-14",
 "tags":{"global":"9/14(월) 미국장 마감","domestic":"9/14 종가"},
 "prices":{
   "KOSPI":{"close":6692.61,"open":6692.61,"open_date":"2026-09-14","pct_screen":-3.14,"cm":""},   ← open = 직전 영업일 시초가(채점용)
   "KOSDAQ":{"close":815.2,"pct_screen":-0.66},                                   ← 표엔 안 나오고 state 에만
   "K200N":{"close":1085.5,"pct_screen":-0.26,"asof":"9/15 05:00","cm":"45자","more":[]},   ← 야간선물. pct 는 페이지의 주간 종가 대비 값
   "SOX":{"close":..,"pct_screen":..,"cm":"45자","more":["..",".."]},  "NVDA":{..}, "MU":{..}, "EWY":{..}, "SKHY":{..},
   "K200F":{..}, "USDKRW":{..}, "005930":{..}, "000660":{..}, "402340":{..}, "009150":{..}, "0167A0":{..}, "442580":{..}},
 "signals":{"news_flag":"주말 큰 뉴스 한 줄 또는 null"},
 "forecast":{"dir":"갭하락","low":6600,"high":6790},
 "tldr":[{"h":"결론 35자","b":"근거 45자","more":["..",".."]}, ×3 정확히],
 "sums":{"global":"50자","domestic":"50자","issue":"50자 (최근 재료 시각 포함)","scen":"50자"},
 "flow":{"foreign":-24587,"inst":-16443,"retail":24259,"other":null,"note":"60자","more":[".."]},   ← 단위 억원, 순매도는 음수
 "bull":[{"t":"제목 25자","d":"설명 45자"},..], "bear":[..],       ← 개수 동일. 상승장이어도 bear 를 채운다
 "ladder":[{"kind":"res","level":7033.92,"d":"근거 40자"},{"kind":"now","level":<코스피 종가>,"d":"9/14 종가 — 장중 고가 6,948.83"},
           {"kind":"sup","level":..,"d":".."},{"kind":"sup2","level":..,"d":".."}],   ← 순서·kind 고정, 4개
 "scenarios":{"base":{"h":"35자","b":"90자","cond":"유지 조건 — 숫자로 검증 가능, 90자"},
              "alt":{"h":"35자","b":"90자","cond":"전환 신호 — 숫자로 검증 가능, 90자"}},
 "why":["아래로 미는 힘 150자","위로 받치는 힘 150자","왜 이 방향인가 150자","구간 폭 근거 150자"],
 "points":[{"t":"확인할 것 25자","d":"판단 기준 60자"}, ×3],
 "checks":{"global":{"lead":"90자 결론","more":[".."]},"domestic":{..},"issue":{..},"scenario":{"lead":"오늘 전망의 가장 약한 고리","more":[".."]}},
 "score":{"open_source":"Google Finance","actual_open":null,"actual_open_date":null,     ← KOSPI.open 의 날짜가 전망 날짜와 다를 때만 채움
          "lead":"무엇이 맞고 틀렸는지 + 실제 시가 숫자, 110자","more":["맞은 것 150자","놓친 것 150자","반복 패턴 150자"]},
 "sources":"출처 — 매체·대상·기준일. 종목별로 어느 두 소스를 대조했는지",
 "data_note":{"lead":"대조 결과 한 줄 (전부 일치면 '종가는 Google Finance와 한국경제에서 일치했습니다.')","more":["갈린 항목의 두 값과 채택 근거"],"diverged":<갈린 항목 수, 정수>}}
```
`cm` 은 모든 종목 필수, "상승 마감" 같은 빈 문장 금지. 회차 번호·날짜 라벨·지난 회차 링크·COVERAGE·채점 띠는 스크립트가 만든다.

## 7. 실행과 검증
```
python3 score.py      # 직전 전망 채점 → calibration.json append (같은 날짜는 두 번 기록하지 않는다)
python3 render.py     # fill.json → out/index.html · out/state.json · out/calibration.json
```
- `FAIL` 이 뜨면 fill.json 을 고쳐 `render.py` 만 다시 돌린다(입력을 안 고치므로 몇 번이든 안전).
- 경고를 읽고 고칠 수 있는 것은 고친다. 특히 **금지 표현·글자 초과·등락률 불일치**. 못 고치는 경고(미확보 등)는 8단계 응답에 적는다.
- 레이아웃: Playwright(chromium) 360·390px 두 폭에서 `out/index.html` 을 열고 `page.evaluate` 로 아래만 받는다. `doc`·`tables` 가 0 이 아니면 종목명(`CONTEXT.md` 표기명)을 줄인다. `height` 가 8,500 을 넘으면 `more` 로 더 옮긴다(2026-09-14 회차 기준 390px 에서 7,800 안팎). Playwright 가 없거나 실패해도 발행한다.
```
({doc: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  tables: [...document.querySelectorAll('.tblwrap')].map(w => w.querySelector('table').scrollWidth - w.clientWidth),
  height: document.documentElement.scrollHeight})
```

## 8. 발행
게이트 — `render.py` 마지막 줄이 `GATE PASS` 일 때만 자동 발행한다. (조건: FAIL 없음 · 금지 표현·글자 초과 경고 0 · 야간선물 확보 · `data_note.diverged` ≤ 2). `GATE HOLD` 면 수동 경로다.
토큰 — Notion 에서 제목이 `jisikin-jogan deploy token` 인 비공개 페이지를 찾아(notion-search → notion-fetch) 본문의 `github_pat_` 또는 `ghp_` 로 시작하는 문자열을 읽는다. 토큰을 응답이나 파일에 적지 않는다.
- 게이트 통과 + 토큰 있음: `GH_TOKEN=<토큰> python3 publish.py --push`. 성공하면 커밋 SHA 를 응답에 적는다.
- 그 외(GATE HOLD, 토큰 없음, push 실패): publish.py 를 돌리지 않는다. `out/` 의 세 파일을 SendUserFile 로 보내고 "다운로드 폴더에 두고 publish.bat" 을 안내한다.
- 자동 발행에 성공해도 세 파일은 SendUserFile 로 함께 보낸다(백업).
- 추가 메시지에 "테스트" 가 있으면 push 하지 않고 `--dry-run` 결과만 보고한다.

## 9. 세션 응답 — 아래만. 인사말·서론·총평 금지
- 시초가 전망 + 예상 구간 한 줄 · 야간선물 값과 시각 · EWY/ADR 시사 갭
- 직전 회차 채점 한 줄 (실제 시가 숫자, hit/miss 근거) · 누적 커버리지 한 줄
- 오늘 가장 중요한 리스크 1건
- 종가 대조 결과 — 일치했는지, 갈린 종목
- render.py 출력 요약(접힘 글자수·경고 건수·경고 제목) / 두 폭 가로 스크롤·높이
- 못 구한 데이터·못 받은 파일
- 발행 결과 — 자동 발행(커밋 SHA) 또는 "받은 세 파일을 다운로드 폴더에 두고 publish.bat 을 실행하면 반영됩니다"
