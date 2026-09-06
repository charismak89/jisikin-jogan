# 종목·데이터 상시 메모

회차마다 이 파일을 읽고 사실관계를 여기에 맞춘다.
프롬프트를 고치지 않고 사실만 갱신할 수 있도록 분리해 둔 파일이다.
새로 확인된 사실은 사람이 추가한다. 회차가 임의로 고치지 않는다.

## SK하이닉스 ADR (SKHY)
- **나스닥 정규 상장 종목이다.** 장외(OTC) 종목이 아니다. 2026-09-04 확인.
- 따라서 "장외라 유동성이 얇다"를 근거로 ADR 신호를 자동으로 할인하지 말 것.
  과거 회차가 이 전제로 ADR을 깎아 읽은 적이 있는데, 잘못된 전제였다.
- 다만 ADR과 MSCI 한국 ETF(EWY)가 반대를 가리킬 때는 **거래대금이 큰 EWY를 우선**한다.
  이 기준은 유동성 차이에서 나온 것이지 상장 시장 때문이 아니다.
- Google Finance 조회: `https://www.google.com/finance/quote/SKHY:NASDAQ`

## 표기용 종목명 (12자 이내, 표 폭 때문에 축약)
| 정식 | 표기 | 코드 |
|---|---|---|
| SOL AI반도체TOP2플러스 | SOL AI반도체TOP2 | 0167A0 |
| PLUS 글로벌HBM반도체 | PLUS 글로벌HBM | 442580 |
| SK하이닉스 ADR | SK하이닉스 ADR | SKHY |

## 소스 우선순위
- 국내 종목·지수·ETF : Google Finance(15:30 종가) 주 + 한국경제 대조
- 코스닥 / 코스피200 선물 / 미 10년물 / WTI : Google Finance 미커버. kr.investing.com
- SOX : kr.investing.com
- 수급 : 언론사 마감시황 기사. 다른 경로가 전부 막혀 있다

## 접근 불가로 확인된 경로 (시도하지 말 것)
- 네이버 증권, KRX, 야후 파이낸스 API, stooq, FnGuide
- 증권사 Open API 전부(토스·키움·한국투자) — 인증이 HTTP 헤더라 WebFetch로 호출 불가
- Twelve Data, stooq — robots.txt 차단

## 재배포 유의
발행 페이지는 public GitHub Pages다. KRX 이용약관 제12조 제2항이 사전 허락 없는
배포·공중송신을 금지한다. `noindex` 유지, "개인 학습용" 문구 유지, 출처 명시 유지.
