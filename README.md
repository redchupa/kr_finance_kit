# 🇰🇷 KR Finance Kit

> **Home Assistant에서 한국·미국 주식, 환율, OpenDart 공시를 네이티브 센서로.**
> 무료 API만 사용. 음성으로 "삼성전자 지금 얼마?" 가능.

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange?style=flat-square)](https://hacs.xyz)
[![Validate](https://img.shields.io/github/actions/workflow/status/redchupa/kr_finance_kit/validate.yml?label=validate&style=flat-square)](https://github.com/redchupa/kr_finance_kit/actions/workflows/validate.yml)
[![Tests](https://img.shields.io/github/actions/workflow/status/redchupa/kr_finance_kit/test.yml?label=tests&style=flat-square)](https://github.com/redchupa/kr_finance_kit/actions/workflows/test.yml)
[![Latest](https://img.shields.io/github/v/release/redchupa/kr_finance_kit?label=release&style=flat-square)](https://github.com/redchupa/kr_finance_kit/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)

---

## ⚡ 3분 안에 동작하는 한국 금융 통합

```
HACS → 사용자 저장소 → https://github.com/redchupa/kr_finance_kit
↓
설정 → 통합 추가 → "KR Finance Kit"
↓
종목코드 입력 (예: 005930, 000660)
↓
sensor.삼성전자 + sensor.sk하이닉스 + 코스피·코스닥·USD/KRW 자동 생성 ✨
```

OpenDart 키(무료)까지 넣으면 **공시 binary_sensor** + **자동 종목명 매핑**(`005930` → `삼성전자`)까지 한 번에.

---

## ✨ 한눈에 보는 기능

| 카테고리 | 상세 |
|---|---|
| **시세 센서** | 코스피·코스닥 지수, USD/KRW 환율, 한국/미국 종목 가격 (모두 yfinance 1소스) |
| **장 운영시간 인식** | 양 시장 모두 닫혀 있으면 폴링 60s → 600s 자동 다이얼다운 (전력·트래픽 절감) |
| **보유 종목 평가** | KR / US 분리 + **KRW 환산 합산** 6개 sensor. `add_position` 서비스로 수량·평단가 입력 (계좌 직연동 X) |
| **OpenDart 공시** | 종목코드만 입력 → `corpCode.xml` 자동 매핑(3,900+ 상장사). 신규 공시 시 binary_sensor ON, 24h 윈도우 |
| **종목명 자동 매핑** | OpenDart 키 있으면 `sensor.kr_005930` 라벨이 자동으로 "삼성전자"로. 사용자 입력 없음 |
| **LLM 도구** | 단일 `finance_query` tool로 8개 query: index/fx/quote/portfolio/disclosures/disclosure_for_ticker/top_movers/market_summary. "오늘 시장 요약해줘" 같은 음성 쿼리 |
| **한국어 UI** | 모든 설정·라벨·설명 한국어 + 영어 fallback. 클릭 가능한 KRX/네이버/Yahoo 검색 링크 내장 |

---

## 🚀 설치

### 1) HACS 사용자 저장소로 추가
1. HACS → 통합 → 우상단 ⋮ → **사용자 저장소**
2. URL: `https://github.com/redchupa/kr_finance_kit`, 카테고리: `Integration`
3. 다운로드 → **HA 재시작**

### 2) 통합 추가
설정 → 기기 및 서비스 → **통합 추가** → "KR Finance Kit"

한 페이지에 모두 입력:

| 필드 | 예시 | 효과 |
|---|---|---|
| **OpenDart API 키** (선택) | `14ab...` | 공시 모니터링 + 종목명 매핑 활성화. [회원가입](https://opendart.fss.or.kr/uss/umt/EgovMberInsertView.do) → [인증키 신청](https://opendart.fss.or.kr/mng/apiUseStusUser.do), 무료·즉시 |
| **한국 종목** (CSV) | `005930, 000660` | KOSPI 6자리 코드. KOSDAQ은 `.KQ` 접미사 (예 `035720.KQ`) |
| **미국 종목** (CSV) | `AAPL, MSFT, TSLA` | 그대로 입력 |
| 코스피·코스닥 지수 포함 | ✓ | 인덱스 sensor 2개 |
| USD/KRW 환율 포함 | ✓ | FX sensor + KRW 환산 portfolio total 활성화 |

### 🔎 종목코드 어디서 찾나요?

| 시장 | 추천 사이트 | 메모 |
|---|---|---|
| 🇰🇷 한국 (6자리) | [KRX 상장법인 목록](https://kind.krx.co.kr/corpgeneral/corpList.do?method=loadInitPage) | 회사명 → 종목코드 검색. KOSPI/KOSDAQ 전체 |
| 🇰🇷 한국 (시세 보면서) | [네이버 금융 시세](https://finance.naver.com/sise/sise_market_sum.naver) | 시가총액 순으로 정렬, URL 끝 6자리가 코드 |
| 🇰🇷 한국 (대안) | [다음 금융](https://finance.daum.net) | 검색·즐겨찾기 친화적 |
| 🇺🇸 미국 (티커) | [Yahoo Finance Lookup](https://finance.yahoo.com/lookup) | 회사명 → 티커 심볼 |
| 🇺🇸 미국 (대안) | [Google Finance](https://www.google.com/finance) | 종목명·티커 같이 표시 |

> 예시: 삼성전자=`005930`, SK하이닉스=`000660`, NAVER=`035420`, 카카오=`035720.KQ`, 애플=`AAPL`, 마이크로소프트=`MSFT`, 테슬라=`TSLA`

이 링크들은 통합 설정 화면 안에도 클릭 가능한 형태로 들어 있어, HA에서 직접 열 수도 있습니다.

자세한 가이드: [docs/installation-ko.md](docs/installation-ko.md)

---

## 📊 만들어지는 센서들

설치 직후 (예: 한국 종목 005930, 000660 + 미국 AAPL, MSFT, OpenDart 키 입력 시):

```
# 시장 지표
sensor.kr_finance_kit_kospi       2,500.12 KRW (+0.50%)
sensor.kr_finance_kit_kosdaq      850.00  KRW (-0.30%)
sensor.kr_finance_kit_usdkrw      1,400.00 KRW

# 한국 종목 — 종목명 자동 매핑
sensor.kr_005930_005930  "삼성전자"   70,000 KRW
sensor.kr_000660_000660  "SK하이닉스" 130,000 KRW

# 미국 종목
sensor.us_aapl_aapl  "US AAPL"  200.00 USD
sensor.us_msft_msft  "US MSFT"  420.00 USD

# 보유 종목 (add_position 서비스 호출 후)
sensor.portfolio_kr_value     한국 보유 평가금액  700,000 KRW
sensor.portfolio_us_value     미국 보유 평가금액  1,000  USD
sensor.portfolio_krw_total    총 평가금액(KRW 환산)  2,100,000 KRW
sensor.portfolio_krw_pl       총 평가손익(KRW 환산)  +240,000 KRW

# 공시
binary_sensor.disclosure_00126380  ON when 삼성전자가 공시 등록 시
```

---

## 🤖 자동화 예시

### 종목 5% 급락 시 텔레그램 알림
```yaml
trigger:
  - platform: numeric_state
    entity_id: sensor.kr_005930_005930
    attribute: change_pct
    below: -5
action:
  - service: notify.telegram
    data:
      message: "{{ trigger.to_state.name }} 급락 {{ state_attr(trigger.entity_id, 'change_pct') }}%"
```

### 장 마감 직후 KRW 환산 일일 요약
```yaml
trigger:
  - platform: time
    at: "15:35:00"
action:
  - service: notify.mobile_app_phone
    data:
      title: "오늘 시장"
      message: >
        KOSPI {{ states('sensor.kr_finance_kit_kospi') }}
        ({{ state_attr('sensor.kr_finance_kit_kospi', 'change_pct') }}%) /
        총 평가금액 {{ states('sensor.portfolio_krw_total') }} KRW
        (손익 {{ states('sensor.portfolio_krw_pl') }} KRW)
```

### 보유 종목에 신규 공시 알림
```yaml
trigger:
  - platform: state
    entity_id: binary_sensor.disclosure_00126380
    to: "on"
action:
  - service: notify.persistent_notification
    data:
      title: "신규 공시"
      message: >
        {{ state_attr(trigger.entity_id, 'report_nm') }}
        {{ state_attr(trigger.entity_id, 'url') }}
```

더 많은 예시: [docs/examples/](docs/examples/)

---

## 🗣️ 음성 쿼리 (HA Voice / Assist)

`finance_query` LLM tool이 자동 등록됩니다. 예시 발화:

| 질문 | 동작하는 query_type |
|---|---|
| "코스피 지수 얼마야?" | `index` |
| "삼성전자 지금 얼마?" | `quote` (ticker=005930) |
| "USD/KRW 환율 알려줘" | `fx` |
| "오늘 보유 종목 중 가장 많이 오른 거?" | `top_movers` |
| "오늘 시장 요약해줘" | `market_summary` — 지수·환율·장 운영 상태·KRW 환산 총평가까지 한 번에 |
| "관심 종목 신규 공시 있어?" | `disclosures` |

---

## 🆓 데이터 소스 (모두 무료)

| 데이터 | 소스 | 인증 |
|---|---|---|
| 코스피·코스닥 | yfinance (`^KS11`, `^KQ11`) | 없음 |
| USD/KRW | yfinance (`KRW=X`) | 없음 |
| 한국 종목 시세 | yfinance (`005930.KS`) | 없음 |
| 미국 종목 시세 | yfinance | 없음 |
| 공시 + 회사명 매핑 | opendart.fss.or.kr (`list.json`, `corpCode.xml`) | 무료 키 |

> yfinance 단일 소스라 스크래핑 의존성 0. 네이버 금융 layout drift / IP 차단 리스크 없음.

---

## 🔒 보안 가드

- **OpenDart 키**는 HA 암호화 ConfigEntry 저장소에만 저장. 소스·로그·테스트 픽스처 어디에도 평문 노출 X.
- **보유 종목**(수량·평단가)은 `kr_finance_kit.add_position` 서비스로만 입력. 증권사 계정 직연동 없음. 레포에 합성 데이터(`your_ticker`, `00000001`)만 존재.
- **NaN/inf 가드** — yfinance가 가끔 보내는 NaN을 두 layer에서 차단(`_safe_float` + `_finite()`). 센서가 unavailable로 떨어지지 않음.
- **장 운영시간 인식** — 양 시장 닫혔을 때 폴링 다운레이팅. yfinance에 폐를 끼치지 않음.

---

## ❌ 의도적 OUT (안 함)

- ❌ **자동 매매** — 법적/약관 리스크. 데이터 표시·알림까지만.
- ❌ **증권사 계좌 직연동** — 비공식 API 보안 리스크.
- ❌ **차트 카드** — [apexcharts-card](https://github.com/RomRider/apexcharts-card) 권장 (별도 HACS).
- ❌ **백테스팅** — Home Assistant 본연의 영역이 아님.

---

## 🛣️ 로드맵

| 마일스톤 | 상태 |
|---|---|
| **M0** 골격 + CI | ✅ |
| **M1** yfinance 일원화 + 멀티 sensor + OptionsFlow | ✅ |
| **M2** 보유 종목 KR/US/KRW + OpenDart 공시 + 장 시간 다이얼다운 | ✅ |
| **M3** LLM tool 8 queries + HACS 등록 PR + in-tree brand 자산 | ✅ |
| **다음** 한국 공휴일 라이브러리 통합, OpenDart 재무지표 sensor, pytest-homeassistant 풀패스 테스트 | 검토 중 |

---

<details>
<summary>📘 English summary</summary>

A Home Assistant HACS integration exposing Korean financial data as native sensors — KOSPI/KOSDAQ indices, USD/KRW FX, Korean and US ticker prices, holdings P/L (KRW-converted), OpenDart corporate disclosures — and a `finance_query` LLM tool for voice queries like "What's Samsung Electronics trading at?".

All data sources are free (yfinance + OpenDart's free key). No brokerage credentials anywhere in the codebase. Polling automatically slows from 60s to 600s when both KR and US markets are closed.

See [docs/installation-en.md](docs/installation-en.md) for setup.

</details>

---

## 💝 후원

이 통합이 도움이 되었다면 ☕ 커피 한잔으로 응원해주세요.

- **토스: 1000-1261-7813**

각 HA 기기 패널의 manufacturer/model/sw_version 필드에도 후원 메타가 노출됩니다 (`우*만 / 토스 1000-1261-7813 / 커피 한잔은 사랑입니다 ☕`).

---

## 📝 License

[MIT](LICENSE) — 자유롭게 사용·수정·재배포 가능.

---

<sub>🤝 버그 리포트·기능 제안: [Issues](https://github.com/redchupa/kr_finance_kit/issues) | 📦 변경 이력: [Releases](https://github.com/redchupa/kr_finance_kit/releases)</sub>
