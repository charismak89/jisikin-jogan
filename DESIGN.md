# DESIGN — 지식인 조간 화면 규칙

이 저장소는 표준 A(원티드 몽타주, 정보형 화면)로 옮기는 중이다(2026-11-26 시작). 표준 A 의 원본은 `charismak89/mock-invest-bot` 의 `DESIGN.md`, `web/scripts/gen-tokens.mjs`, `web/src/components/ui/` 다.
- 실험실(`web/src/labs/`, 주소 `/labs/`)은 표준 A 로 그린다. 1절과 2-1을 따른다.
- 메인 v6(`web/src/App.tsx`, `components/`, 루트 `index.html`, `v6/`)는 아직 옛 토스풍 토큰이다. 2-2를 따른다. 실험실을 메인으로 전환하는 PR 에서 2-2와 옛 코드를 지운다.
- 한 화면 안에 옛 토큰과 몽타주 토큰을 섞지 않는다. 실험실이 쓰던 공유 컴포넌트는 `web/src/labs/components/` 로 복사해 고쳤다.
- 지난 회차 HTML(`archive/`)과 그 스타일(`style.css`, `template-v5.html`)은 바꾸지 않으므로 이 규칙을 넣지 않는다.
고치는 절차(빌드, regress, uicheck, uishots)는 `.claude/rules/web.md` 에 있다. 토큰 갱신은 `cd web && npm run tokens`(생성 파일은 손으로 고치지 않는다), 확인은 `npm run tokens:check`(build 가 먼저 돈다).

## 1. 공통 규칙 (표준 A 저장소 같은 글)

이 절을 고치면 표준 A 를 쓰는 다른 저장소 `DESIGN.md` 1절도 같은 날 같은 글로 고친다. 저장소마다 다른 값은 2절 이하에 쓴다.

색
- 컴포넌트에는 색 값을 직접 쓰지 않는다. `index.css` `@theme inline` 이름(`bg-card`, `text-fg-2`, `text-up` 등)만 쓴다. 차트 SVG 도 `var(--mt-…)` 로 칠한다.
- 바탕은 `bg-bg-2`(옅은 회색), 카드는 `bg-card`(흰색), 행동은 파랑 하나(`bg-brand`)다. 몽타주처럼 면을 색으로 칠하지 않고 얇은 선(`ring-line-2`)과 옅은 채움(`bg-fill`)으로 나눈다.
- 등락은 `text-up`(빨강), `text-down`(파랑), `text-flat`만 쓴다. 국내 증시 관례다. `negative`(빨강)는 오류와 실패에만 쓴다. 등락과 오류를 같은 토큰으로 칠하지 않는다.
- 색만으로 뜻을 전하지 않는다. 등락은 부호와 ▲▼, 상태는 점과 글자를 같이 쓴다(`Badge`).
- 다크는 같은 토큰 이름에 몽타주 다크 값을 덮는다. 테마는 시스템, 라이트, 다크 셋이고, 첫 화면 전에 `index.html` 인라인 스크립트가 `data-theme` 을 정한다.

대비 (WCAG 2.1 AA: 18px 미만 4.5:1, 18px 이상 굵은 글자 3:1)
- 정보가 되는 글자는 `text-fg`, `text-fg-2` 로 쓴다.
- `text-fg-3`(몽타주 tertiary, 라이트 3.67:1)은 18px 이상 글자나 없어도 되는 보조 표시에만 쓴다.
- `text-positive`(초록, 라이트 2.46:1)는 글자에 쓰지 않는다. 점, 아이콘, 옅은 배경(`bg-positive-subtle`)에만 쓴다.
- 배지(12px) 글자는 모두 `text-fg` 다. 상태 색은 점과 옅은 바탕으로만 나눈다. 색 글자는 옅은 바탕 위에서 4.5:1 이 안 나온다(라이트 brand-fg 4.49).
- 주 단추는 `bg-brand-btn` 이다. 라이트는 brand.primary, 다크는 brand.heavy 다. 다크 brand.primary(#3385FF) 위 흰 글자는 3.54:1 이다.
- 토큰이나 패키지 버전을 바꾸는 PR 에는 `--report` 결과를 붙인다.

글자 (몽타주 타입 스케일, Tailwind `text-<이름>`)
- `title1` 32, `title3` 24: 첫 화면 결론, 숫자 타일
- `heading2` 20, `headline1` 18: 카드 제목
- `body1` 16, `body2` 15: 본문, 목록
- `label1` 14, `label2` 13: 라벨, 칩, 보조 값
- `caption1` 12: 캡션, 배지
- 굵기: 숫자와 제목 700, 라벨 600, 본문 400~500. 숫자에는 `.num`(tabular-nums)을 붙인다. 한국어 문장은 `word-break: keep-all`.

숫자 표기 (`web/src/lib/fmt.ts`)
- 천 단위 쉼표(`ko-KR`). 양수 `+`, 음수 `−`(U+2212), 0 은 부호 없음.
- 시각은 KST. 값이 없으면 `-` 처럼 비었다는 것이 드러나게 쓴다. 0 으로 채우지 않는다.

배치
- 본문 최대 폭 1120px. 좌우 여백 16px, 640px 부터 24px. 1024px 부터 2단.
- 카드: 모서리 16px(`rounded-lg`), 안쪽 여백 20px(640px 부터 24px), 그림자 `shadow-xs`. 단추: 48 / 40 / 32px 높이, 모서리 12 / 10 / 8px(몽타주 Button 규격).
- 그리드는 `grid-cols-1`(minmax(0,1fr))부터 쓴다. 390px 폭에서 가로 스크롤 0.

컴포넌트 (`web/src/components/ui/`)
- 있는 것: `Button`(primary, secondary, assistive), `Card`, `CardHeader`, `Badge`, `Tabs`, `Stat`.
- 새로 만들 때: 몽타주 문서(montage.wanted.co.kr)에서 같은 이름 컴포넌트의 규격(크기, 상태, 이름)을 먼저 찾고 따른다. 없으면 shadcn 구조로 만든다.

## 2. 이 저장소 값

### 2-1. 실험실 (표준 A, 2026-11-26, `@montage-ui/theme` 4.4.0)

파일
- `web/src/styles/montage.css`: `scripts/gen-tokens.mjs` 생성(모의투자 봇 원본과 같은 스크립트, 같은 결과).
- `web/src/labs/montage-night.css`: `scripts/gen-night.mjs` 생성. 첫 카드 밤 하늘(`data-sky="night"`)에 몽타주 다크 값을 그 카드 안에서만 덮는다. 몽타주 생성 파일은 다크 값을 `:root` 에만 걸어, 라이트 테마에서도 남색인 밤 카드에 쓸 수 없어서 만들었다.
- `web/src/labs/labs.css`: 실험실 스타일 입구. `@theme inline` 대응은 모의투자 봇 `web/src/styles/index.css` 와 같은 글이고, 그 뒤에 이 저장소 확장만 더한다.
- `web/src/labs/components/ui/`: 모의투자 봇 `Button`, `Card`, `Badge`, `Tabs` 그대로. `Card` 에 캡션 `Cap` 만 더했다.
- `web/src/labs/lib/cn.ts`: tailwind-merge 에 몽타주 글자 크기 이름을 알려 준 `cn`. 원본 `cn` 은 `text-caption1` 과 `text-fg` 가 같이 오면 글자 크기를 지운다(2026-11-26 확인, 원본 저장소에 알릴 일).
- `web/src/labs/lib/tone.ts`: 등락 색 클래스(`text-up`, `text-down`). 공용 `lib/fmt.ts` 의 `dir()` 는 옛 이름(`text-dn`)이라 실험실은 쓰지 않는다.
- 테마: `data-theme`(라이트, 다크를 골랐을 때만 적고 시스템이면 비운다). 저장 키는 메인과 같은 `jj-theme`. 글꼴은 npm `pretendard` 를 빌드에 넣는다(외부 요청 없음).

토큰 대응 (`web/src/styles/index.css`)

| Tailwind 이름 | 몽타주 토큰 | 쓰임 |
| --- | --- | --- |
| `bg`, `bg-2` | background.neutral.primary, secondary | 화면 바탕 |
| `card` | surface.elevated.primary | 카드 |
| `fill`, `fill-strong` | surface.neutral.secondary, strong | 옅은 채움, 탭 바탕 |
| `fg`, `fg-2`, `fg-3` | foreground.neutral.primary, secondary, tertiary | 글자 |
| `line`, `line-2` | line.neutral.primary, secondary | 선 |
| `brand`, `brand-strong`, `brand-subtle`, `brand-fg` | surface.brand.*, foreground.brand.primary | 행동 |
| `positive`, `cautionary`, `negative` (+ `-subtle`) | foreground.*, surface.* | 상태 |
| `up`, `down`, `flat` | 생성 스크립트의 금융 토큰(red 40/60, blue 40/60, neutral.secondary) | 등락, 보합 |
| `on-brand`, `brand-btn` | static.white, `--btn-brand`(라이트 brand.primary, 다크 brand.heavy) | 주 단추 |
| `rounded-10` | radius.10 | 단추 medium, 탭 |

이 저장소 확장 (`labs.css` 끝, 몽타주 토큰을 섞어 만들고 값을 새로 적지 않는다)

| Tailwind 이름 | 만드는 법 | 쓰임 |
| --- | --- | --- |
| `inverse` | surface.neutral.inverse | 실험실 띠, 차트 말풍선 바탕(글자는 `text-fg-inverse`) |
| `scrim` | static.black 40% | 의견 창 뒤 어둡게 |
| `band`, `band-line` | foreground.cautionary 28%, foreground.cautionary | 07:45 예상 구간 띠와 선(옛 화면의 노란 띠) |

첫 카드 예외 (`web/src/labs/sky.css`)
- 시간대 하늘 그라데이션(새벽, 낮, 저녁, 밤과 각 다크)은 몽타주에 없어 이 파일에만 값을 적는다. 다른 카드에는 쓰지 않는다.
- 카드 안 글자와 등락색은 몽타주 토큰 그대로다. 하늘 위에 바로 놓이는 색 글자는 32px 숫자(`text-title1`)뿐이고, 작은 등락 숫자(종목 칸)는 흰 칸(`bg-card`) 위에 둔다.
- 상태 점: 장중 `fin-up`, 그 밖 accent.violet, 밤 foreground.cautionary. 점 옆에 글자가 같이 나온다.

대비 (2026-11-26 계산, 반투명 토큰은 바탕에 섞어서 잼)

| 조합 | 최소값 | 기준 |
| --- | --- | --- |
| `fg-2` 작은 글자, 라이트 하늘 5색 위 | 7.98 | 4.5 |
| `fg-2`(다크 값), 어두운 하늘 9색 위 | 7.06 | 4.5 |
| 큰 숫자 `up` / `down`, 라이트 하늘 위 | 3.88 / 5.57 | 3 (32px 굵은 글자) |
| 큰 숫자 `up` / `down`, 어두운 하늘 위 | 5.23 / 4.31 | 3 |
| 작은 등락 숫자, 흰 칸 / 다크 칸(#212225) 위 `up` | 4.58 / 5.47 | 4.5 |
| 작은 등락 숫자, 다크 칸 위 `down` | 4.50 | 4.5 (경계값) |

- 옛 화면의 캡션색(`--tx3`) 자리는 모두 `text-fg-2` 다. 몽타주 `fg-3`(3.67:1)은 입력 칸 안내 글자(placeholder)와 진행 막대처럼 없어도 되는 표시에만 썼다.
- 브리핑 전문(`web/src/labs/brief.css`, Shadow DOM): 본문 HTML 의 인라인 SVG 가 옛 이름(`--tx2`, `--tx3`, `--line`, `--line2`, `--ok`, `--panel`)을 쓰므로 `:host` 에서 그 이름을 몽타주 토큰으로 잇는다. 초록, 주황 글자는 4.5:1 이 안 나와 글자는 본문색으로 두고 색은 바탕과 점으로만 쓴다. 카드 왼쪽에 색 띠(left border accent)를 두지 않는다(2026-11-27 하방 체크에서 뺐다).

### 2-2. 메인 v6 (옛 토스풍, 전환 PR 에서 지움)

### 2-2-1. 옛 공통 규칙

두 저장소는 화면 결만 같다. 저장소·테마 키·발행 주소·빌드 산출물은 섞지 않는다.
2026-11-26 표준 A 로 1절을 바꾸기 전의 글이다. 메인 v6 만 이 규칙을 따른다. 고치지 않고 전환 PR 에서 지운다.

색
- 연회색 바탕(`--bg`) 위 흰 카드(`--card`), 강조는 파랑(`--brand`).
- 상승 빨강(`--up`) · 하락 파랑(`--dn`). 국내 증시 관례다.
- 색만으로 뜻을 전하지 않는다. 등락은 부호와 ▲▼, 상태는 점과 글자(정상·실패·미확인)를 같이 쓴다.
- 컴포넌트에 색 값을 직접 쓰지 않는다. `index.css` `:root` 토큰과 Tailwind `@theme inline` 이름(`text-tx3`, `bg-card` 등)만 쓴다. 차트 SVG 도 `var(--…)` 로 칠한다.
- 다크는 같은 토큰 이름에 다크 값을 덮는다. 테마는 시스템·라이트·다크 세 가지이고, 첫 화면이 그려지기 전에 `index.html` 인라인 스크립트가 정한다.
- 글자 대비 목표는 WCAG 2.1 AA 다. 18px 미만 글자는 4.5:1, 18px 이상 굵은 숫자는 3:1. 토큰을 바꾸는 PR 에는 흰 카드·`--bg`·다크 카드 위 대비를 계산해 적는다.

글자
- 크기는 px 로 적는다(`text-[13px]`). 단계: 11 배지 · 12 캡션 · 13 보조·칩 · 14 본문·표 · 15~16 강조 문장 · 17 카드 제목 · 18~24 숫자 타일 · 26~32 첫 화면 결론 한 줄.
- 굵기: 숫자·제목은 700(bold)·800(extrabold), 라벨은 600(semibold), 본문은 400~500.
- 숫자에는 `.num`(tabular-nums)을 붙여 자릿수를 맞춘다.
- 한국어 문장은 `word-break: keep-all` 로 단어 중간에서 줄을 바꾸지 않는다.

숫자 표기
- 천 단위 쉼표(`ko-KR`). 양수는 `+`, 음수는 `−`(U+2212), 0 은 부호 없음.
- 시각은 KST. `MM/DD HH:mm` 또는 `HH:mm`, 날짜만이면 `M/D`.
- 값이 없으면 `-` 나 '미확보'처럼 비었다는 것이 드러나게 쓴다. 0 으로 채우지 않는다.
- 등락률 소수 자릿수와 금액 단위는 저장소마다 다르다(3절).

배치
- 본문 최대 폭 1120px. 좌우 여백 16px, 640px 부터 24px. 1024px 부터 2단.
- 카드: 모서리 24px(`rounded-3xl`), 안쪽 여백 20px(640px 부터 24px). 카드 제목 17px bold, 오른쪽 보조 13px `--tx3`, 아래 캡션 12px `--tx3`.
- 그리드는 `grid-cols-1`(minmax(0,1fr))부터 쓴다. 열 너비가 없으면 넓은 표가 열을 밀어 모바일 폭이 깨진다.
- 390px 폭에서 가로 스크롤 0.

### 2-2-2. 옛 토큰 값 (`web/src/index.css`, 2026-10-31)

| 토큰 | 라이트 | 다크 | 쓰임 | 흰 카드 / 다크 카드 대비 |
| --- | --- | --- | --- | --- |
| `--bg` | #f2f4f6 | #101114 | 페이지 바탕 | |
| `--card` · `--card2` | #ffffff · #f9fafb | #1b1d22 · #23262c | 카드 · 칩·탭 바탕 | |
| `--tx` | #191f28 | #f2f4f6 | 본문·숫자 | 16.6 / 15.3 |
| `--tx2` | #4e5968 | #b0b8c1 | 보조 본문 | 7.1 / 8.4 |
| `--tx3` | #6b7684 | #7e8793 | 캡션·라벨 | 4.6 / 4.6 |
| `--line` | #e5e8eb | #2c3037 | 구분선 | |
| `--brand` · `--brand-soft` | #3182f6 · #e8f3ff | #4593fc · #1c2a3d | 강조·링크·차트 선 | 3.7 / 5.5 |
| `--up` | #e42939 | #f6616d | 상승 | 4.5 / 5.5 |
| `--dn` | #1b64da | #5b9dff | 하락(`--brand` 와 다른 값) | 5.4 / 6.2 |
| `--ok` | #15b573 | #2fd08c | 정상 | 2.7 / 8.5 |
| `--band` · `--band-line` | #ffe9a8 · #f5b800 | #4a3b10 · #d9a400 | 예상 구간 띠·선 | |

- 대비는 2026-10-28 계산값이다(WCAG 상대 휘도). `--tx3`·`--up`·`--dn` 은 2026-10-31 값(4절 후속 1·2 반영). `--bg` 위 라이트 대비는 `--tx3` 4.2 · `--up` 4.1 · `--dn` 4.9 로 카드보다 조금 낮다.
- 브리핑 전문 탭(`brief.css`)은 Shadow DOM 안에서 위 토큰을 물려받고, 본문 안 채점 차트용 토큰(`--line2`, `--warn-bg`·`--warn-tx`·`--warn-strong`)만 따로 둔다. 본문 기본 글자 15px, 줄 간격 1.6.
- 테마 키: `data-jj` 속성, localStorage `jj-theme`(v5 때부터 같은 키라 지인이 고른 테마가 이어진다). 코인 집사의 `cb-theme` 와 섞지 않는다.
- 글꼴: Pretendard Variable 웹폰트(jsDelivr `pretendard@v1.3.9` dynamic subset). 못 받으면 `-apple-system` → Apple SD Gothic Neo → Noto Sans KR.

### 2-2-3. 숫자 표기 (`web/src/lib/fmt.ts`, 메인과 실험실 공용)

| 함수 | 예 | 쓰임 |
| --- | --- | --- |
| `sg` | +0.85% · −1.20% | 등락·예상 갭(소수 2자리, 입력이 이미 % 값) |
| `money` | 61,200원 · ≈2,615 | 종목가·지수(호가 단위 `tick` 반올림, 추정치는 `≈`) |
| `nf` | 1,234 | 쉼표 숫자 |
| `dir` · `arrow` | `text-up` · ▲ | 등락 색·화살표 |
| `hm` · `kstDay` · `md` | 09:05 · 2026-10-28 · 10/28 | 장중 시각·날짜(KST) |

- 루틴이 쓰는 데이터 계약은 루트 `day.json` 이다. 화면에서 새 반올림 규칙을 만들면 `render.py`(v5 HTML)와 숫자가 갈린다. 같은 값은 같은 자릿수로 쓴다.

### 2-2-4. 코인 집사와 다른 점, 후속(옛 기록)

| 항목 | 지식인 조간 | 코인 집사 | 판단 |
| --- | --- | --- | --- |
| `--tx3`(캡션) | #6b7684, 4.6:1 (10/31 전 #8b95a1, 3.0) | #6b7684, 4.6:1 | 후속 1 반영(2026-10-31) |
| `--up` · `--dn` | #e42939 4.5 · #1b64da 5.4 (10/31 전 #f04452 · #3182f6, 3.7) | #e42939 4.5 · #1b64da 5.4 | 후속 2 반영(2026-10-31). 다크 `--dn` 도 코인 집사 #5b9dff |
| 하락 = 강조색 | 다른 파랑(10/31 전 같은 값) | 다른 파랑 | 후속 2 반영. 예측 구간 꼬리표 '안'(brand)과 '아래'(dn)가 갈린다 |
| `--ok` | #15b573, 2.7:1 | #0f8a54, 4.4:1 | 둘 다 4.5 미만 |
| 글꼴 | Pretendard 웹폰트 | 시스템 글꼴 | 의도된 차이 |
| 등락률 소수 | 2자리 | 1자리 | 유지 |
| 다크(스크립트 꺼짐) | `data-jj` 만 봄 | `prefers-color-scheme` 대비 있음 | 후속 3(작음) |
| `keep-all` | 브리핑 탭에만 | 앱 전체(`html`) | 후속 3 |

후속 후보(1·2 는 2026-10-31 주간 점검 승인으로 반영. 3 은 v6 가 스크립트 없이 그려지지 않아 올리지 않는다)
1. `--tx3` 라이트 값을 #6b7684 로 바꾼다. 흰 카드 3.0 → 4.6. 회색 캡션이 조금 진해진다.
2. `--up` #e42939, `--dn` #1b64da 로 바꾸고 `--dn` 을 `--brand` 와 떼어 낸다. 두 저장소 등락 색이 같아진다. `archive/` 는 `style.css` 를 쓰므로 영향 없음.
3. `index.css` 에 `prefers-color-scheme` 다크 대비와 `html { word-break: keep-all }` 을 넣는다.
- 셋 다 `web/` 만 바꾸고 `uicheck.py`·`uishots.py` 다크·라이트 사진으로 확인한다.
