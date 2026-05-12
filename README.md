# KR Finance Kit

> Home Assistant 통합 — 한국 주식·환율·OpenDart 공시·미국 주식을 네이티브 센서로.

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![Validate](https://github.com/redchupa/kr_finance_kit/actions/workflows/validate.yml/badge.svg)](https://github.com/redchupa/kr_finance_kit/actions/workflows/validate.yml)
[![Tests](https://github.com/redchupa/kr_finance_kit/actions/workflows/test.yml/badge.svg)](https://github.com/redchupa/kr_finance_kit/actions/workflows/test.yml)

🚧 **M3 (LLM tool 확장 완료)** — 외부 단계만 남음: GitHub repo push → hacs/default PR → home-assistant/brands PR. 절차는 [HACS_SUBMISSION.md](HACS_SUBMISSION.md).

## 무엇을 하나

- **지수 센서**: 코스피·코스닥 (yfinance `^KS11`/`^KQ11`)
- **환율 센서**: USD/KRW
- **종목 시세 센서**: 한국(`005930` → `005930.KS` 자동 변환) + 미국
- **보유 종목 평가손익**: KR / US / **KRW 환산 합산** 6개 센서 — 수량·평단가는 `add_position` 서비스로 입력 (계좌 연동 X)
- **공시 binary_sensor**: 관심 종목에 신규 공시 시 ON. 종목코드만 입력해도 corp_code 자동 변환.
- **장 운영시간 인식**: 한·미 장 모두 닫혀 있으면 폴링 60s → 600s 자동 다이얼다운 (전력·yfinance 부하 절감)
- **LLM 도구**: `finance_query` 한 개로 8가지 query — index, fx, quote, portfolio, disclosures, disclosure_for_ticker, top_movers, market_summary. "삼성전자 지금 얼마?", "오늘 보유 종목 중 가장 많이 오른 것?", "오늘 시장 요약해줘" 같은 음성 쿼리 가능

## 설치

자세한 설치는 [docs/installation-ko.md](docs/installation-ko.md). HACS 사용자 저장소로 추가 후 통합 추가 화면에서 OpenDart 키·티커를 입력합니다.

```yaml
# 자동화 예시 — 종목 5% 하락 알림
trigger:
  - platform: numeric_state
    entity_id: sensor.kr_finance_kit_kr_your_ticker
    attribute: change_pct
    below: -5
```

더 많은 예시: [docs/examples/automation-examples.yaml](docs/examples/automation-examples.yaml)

## 보안

- **OpenDart 키**는 HA 암호화 저장소에만 저장됩니다. 레포·로그·이슈 어디에도 평문 노출 X.
- 보유 종목 수량·평단가는 **사용자가 직접 서비스 호출로 입력** — 증권사 계정 직연동 없음.
- 모든 예시·테스트 픽스처는 합성 데이터 (`your_ticker`, `00000001`).

자세한 보안 가드는 [PLAN.md §7](PLAN.md).

## 데이터 소스 (모두 무료)

| 데이터 | 소스 | 인증 |
|---|---|---|
| 코스피·코스닥 | yfinance (`^KS11`, `^KQ11`) | 없음 |
| USD/KRW | yfinance (`KRW=X`) | 없음 |
| 한국 종목 시세 | yfinance (`005930.KS`) | 없음 |
| 미국 종목 시세 | yfinance | 없음 |
| 공시 | opendart.fss.or.kr (`list.json`, `company.json`) | 무료 키 |

> 본 통합은 `daily_market.py` 자산에서 검증된 yfinance 단일 소스로 일원화되어 있습니다. 스크래핑 의존성이 없어 layout drift / IP 차단 리스크가 없습니다.

## 범위 외 (의도적)

- ❌ 자동 매매
- ❌ 증권사 계좌 직연동
- ❌ 차트 카드 (apexcharts-card 사용 권장)
- ❌ 백테스팅

## 로드맵

- **M0** 골격 + CI ✅
- **M1** yfinance 일원화 + OptionsFlow + key 검증 ✅
- **M2** 보유 종목(KR/US/KRW 환산) + 공시 + 장 운영시간 다이얼다운 + stock_code 자동 변환 ✅
- **M3** LLM tool 확장 + HACS default repo PR + brand/icon

---

<details>
<summary>English summary</summary>

A Home Assistant integration exposing Korean financial data — KOSPI/KOSDAQ indices, USD/KRW FX, Korean and US stock quotes, holdings P/L, and OpenDart disclosures — as native sensors, with an LLM tool for voice queries.

All data sources are free. The OpenDart API key is stored only in HA's encrypted config; nothing financial-private (holdings, brokerage credentials) ships in this repo. See [docs/installation-en.md](docs/installation-en.md).

</details>

## 후원

이 통합이 도움이 되었다면 ☕ 커피 한잔으로 응원해주세요.

- 토스: **1000-1261-7813**

각 HA 기기 패널의 manufacturer/model 필드에도 후원 메타가 노출됩니다.

## License

[MIT](LICENSE).
