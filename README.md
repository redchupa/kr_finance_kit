# KR Finance Kit

**[English](README.en.md)** · 한국어

> **Home Assistant 대시보드에 한국·미국 주식이 뜬다.**
> 음성으로 "삼성전자 지금 얼마?"
> 보유 종목 떨어지면 자동 알림.

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-FF8C00?style=flat-square&logo=homeassistantcommunitystore&logoColor=white)](https://hacs.xyz)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.6%2B-03A9F4?style=flat-square&logo=home-assistant&logoColor=white)](https://www.home-assistant.io)
[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-43A047?style=flat-square)](LICENSE)

[![Validate](https://img.shields.io/github/actions/workflow/status/redchupa/kr_finance_kit/validate.yml?label=validate&style=flat-square&logo=github)](https://github.com/redchupa/kr_finance_kit/actions/workflows/validate.yml)
[![Tests](https://img.shields.io/github/actions/workflow/status/redchupa/kr_finance_kit/test.yml?label=tests&style=flat-square&logo=github)](https://github.com/redchupa/kr_finance_kit/actions/workflows/test.yml)
[![Data: yfinance](https://img.shields.io/badge/data-yfinance-7B1FA2?style=flat-square&logo=yahoo&logoColor=white)](https://github.com/ranaroussi/yfinance)
[![Disclosures: OpenDart](https://img.shields.io/badge/disclosures-OpenDart-E53935?style=flat-square)](https://opendart.fss.or.kr)
[![Made for HA](https://img.shields.io/badge/Made%20for-Home%20Assistant-18BCF2?style=flat-square&logo=home-assistant&logoColor=white)](https://www.home-assistant.io)

[Releases](https://github.com/redchupa/kr_finance_kit/releases)

---

## 이런 분들께

- ☕ **아침에 출근하면서** 휴대폰 보지 않고도 거실 패널에서 코스피·내 종목 현황 한눈에
- 📉 **보유 종목 5% 떨어지면** 즉시 텔레그램·카톡으로 알림
- 🗣️ **자녀나 가족도** "헤이구글, 삼성전자 얼마야?" 음성으로 물어볼 수 있게
- 🔔 **장 마감 직후 자동으로** 오늘 시장 요약·평가손익을 한 줄 메시지로
- 📋 **새 공시 뜨면** 휴대폰 알림 (감사·임원변동·실적발표 등 놓치지 않기)

이 모든 게 **무료 API**로, 증권사 계정 연동 없이 가능합니다.

---

## ⚡ 5분이면 끝나는 설치

### 사전 준비 (이미 되어 있다면 건너뛰세요)

- ✅ Home Assistant 설치
- ✅ [HACS](https://hacs.xyz) 설치 (HA 통합·카드 마켓플레이스)

### Step 1 · HACS에 저장소 추가

1. HA 좌측 메뉴에서 **HACS** 클릭
2. 우상단 ⋮ 메뉴 → **사용자 정의 저장소** (Custom repositories)
3. 다음 입력:
   - **저장소 URL**: `https://github.com/redchupa/kr_finance_kit`
   - **유형**: `Integration`
4. **추가** 클릭

### Step 2 · 다운로드

1. HACS 메인 화면에서 **KR Finance Kit** 검색
2. 카드 클릭 → 우하단 **다운로드** → 확인
3. **Home Assistant 재시작** (설정 → 시스템 → 다시 시작)

### Step 3 · 통합 추가

1. **설정** → **기기 및 서비스** → 우하단 **+ 통합 추가**
2. **"KR Finance Kit"** 검색 → 클릭
3. 한 페이지에 다음 입력 (모두 선택사항, 비워둬도 OK):

   | 입력란 | 무엇인가요? | 예시 |
   |---|---|---|
   | **OpenDart API 키** | 공시 알림 + 종목명 자동 표시용 (비워두면 가격만 표시) | `14ab...` (아래 발급 안내) |
   | **한국 종목 코드** | 보고 싶은 종목들. 쉼표로 구분 | `005930, 000660, 035420` |
   | **미국 종목 심볼** | 미국 주식. 쉼표로 구분 | `AAPL, MSFT, TSLA` |
   | **암호화폐·환율·선물** | Yahoo ticker 형식. 시장 시간 무관 24/7 갱신. | `BTC-USD, ETH-USD, EUR=X, GC=F` |
   | 코스피·코스닥 지수 포함 | 체크하면 한국 지수 sensor 생성 | ☑ |
   | 나스닥·다우·S&P 500 지수 포함 | 체크하면 미국 지수 sensor 생성 | ☑ |
   | USD/KRW 환율 포함 | 체크하면 환율도 표시 | ☑ |

4. **확인** → 완료!

설정 화면 안에 **클릭 가능한 검색 링크**가 들어 있어, 종목 코드 모르셔도 바로 찾으실 수 있습니다.

---

## 🔎 종목 코드 찾기

처음이라 코드를 어떻게 입력해야 할지 모를 때:

### 한국 종목 (6자리 숫자)

가장 쉬운 방법은 **네이버 금융**에서 회사 검색 → URL 끝의 6자리 숫자가 종목코드.

| 회사 | 코드 |
|---|---|
| 삼성전자 | `005930` |
| SK하이닉스 | `000660` |
| NAVER | `035420` |
| 카카오 | `035720.KQ` _← KOSDAQ은 끝에 `.KQ` 붙이기_ |
| LG에너지솔루션 | `373220` |
| 현대차 | `005380` |
| 기아 | `000270` |

추천 검색 사이트: [KRX 상장법인 목록](https://kind.krx.co.kr/corpgeneral/corpList.do?method=loadInitPage) · [네이버 금융](https://finance.naver.com/sise/sise_market_sum.naver) · [다음 금융](https://finance.daum.net)

### 미국 종목 (영문 티커)

| 회사 | 코드 |
|---|---|
| 애플 | `AAPL` |
| 마이크로소프트 | `MSFT` |
| 테슬라 | `TSLA` |
| 엔비디아 | `NVDA` |
| 알파벳(구글) | `GOOGL` |
| 아마존 | `AMZN` |

추천 검색 사이트: [Yahoo Finance Lookup](https://finance.yahoo.com/lookup) · [Google Finance](https://www.google.com/finance)

---

## 🔑 OpenDart 키 받기 (선택, 무료, 1분)

OpenDart는 한국 금융감독원의 무료 공시 API입니다. 키를 넣으면 두 가지가 추가됩니다:

- ✨ **종목명 자동 표시** — `sensor.fi_kr_005930`이 자동으로 "삼성전자"로 표시
- 📋 **신규 공시 알림** — 관심 종목에 공시 뜨면 binary_sensor가 ON

**받는 법**:
1. [opendart.fss.or.kr 회원가입](https://opendart.fss.or.kr/uss/umt/EgovMberInsertView.do)
2. 로그인 후 [인증키 신청](https://opendart.fss.or.kr/mng/apiUseStusUser.do)
3. 즉시 발급된 키를 복사해서 통합 추가 화면에 붙여넣기

**키 없이도 가격·환율 sensor는 완전히 동작합니다.** 부담 없이 나중에 추가하셔도 OK.

---

## 📊 무엇이 만들어지나요?

예를 들어 한국 종목 `005930, 000660`, 미국 `AAPL`, OpenDart 키를 입력하면:

```
시장 지표 ────────────────────────────────────────
  코스피                        2,500.12  (+0.50%)
  코스닥                          850.00  (-0.30%)
  USD/KRW                       1,400.00  (+0.10%)

한국 종목 ────────────────────────────────────────
  삼성전자                       70,000원  (+1.5%)
  SK하이닉스                    130,000원  (-2.0%)

미국 종목 ────────────────────────────────────────
  AAPL                          $200.00   (+3.0%)

보유 종목 (수량·평단가 입력 시) ──────────────────
  한국 보유 평가금액                       700,000원
  미국 보유 평가금액                          $1,000
  💰 총 평가금액 (KRW 환산)              2,100,000원
  📈 총 평가손익 (KRW 환산)               +240,000원

공시 알림 ────────────────────────────────────────
  🔔 삼성전자 신규 공시  ← 등록 시 자동 ON
```

이 모든 항목이 **HA 센서**라서 대시보드 카드·자동화·음성쿼리에 자유롭게 사용할 수 있습니다.

---

## 🎯 첫 자동화 만들기

가장 간단한 예시 — **종목이 5% 이상 떨어지면 알림**:

```yaml
alias: "삼성전자 급락 알림"
trigger:
  - platform: numeric_state
    entity_id: sensor.fi_kr_005930   # ← 본인 종목으로 교체
    attribute: change_pct
    below: -5
action:
  - service: notify.mobile_app           # ← 본인 알림 서비스로 교체
    data:
      title: "📉 급락 알림"
      message: "{{ trigger.to_state.name }} {{ state_attr(trigger.entity_id, 'change_pct') }}% 하락"
```

더 많은 자동화 예시(장 마감 일일 요약, 공시 알림 등)는 [docs/examples/](docs/examples/) 폴더에 있습니다.

---

## 🧩 블루프린트로 알림 자동화

**관심 종목을 여러 개 등록해놓고, 어떤 종목만 알림을 받을지 체크박스로 골라 쓰는 방식**입니다. 종목을 빼고 넣을 때 자동화를 새로 만들 필요 없이 블루프린트 입력만 수정하면 됩니다.

블루프린트 두 개를 제공합니다:

### 1. 종목 가격 변동률 알림

선택한 종목 중 어느 하나라도 임계값(예 +5% / -5%)을 넘으면 푸시.

[![내 Home Assistant에서 블루프린트 import 열기](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fredchupa%2Fkr_finance_kit%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fkr_finance_kit%2Fprice_change_alert.yaml)

수동 import용 URL: `https://github.com/redchupa/kr_finance_kit/blob/main/blueprints/automation/kr_finance_kit/price_change_alert.yaml`

입력 항목: 알림 받을 종목(여러 개 선택) · 하락 임계값(예 -5) · 상승 임계값(예 5) · **알림 보낼 대상**(mobile_app 등 notify entity, 드롭다운에서 검색·선택).

### 2. 일일 시장 요약

지정한 시각(기본 한국 장 마감 15:30)에 코스피·코스닥·환율·선택 종목·보유 종목 평가손익을 한 메시지로 발송.

[![내 Home Assistant에서 블루프린트 import 열기](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fredchupa%2Fkr_finance_kit%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fkr_finance_kit%2Fdaily_summary.yaml)

수동 import용 URL: `https://github.com/redchupa/kr_finance_kit/blob/main/blueprints/automation/kr_finance_kit/daily_summary.yaml`

### import 방법 (둘 다 동일)

1. 위 **"블루프린트 import 열기"** 버튼 클릭 → HA가 import 다이얼로그 자동 표시
2. 또는 **설정 → 자동화 및 장면 → 블루프린트 → 블루프린트 import** 에 위 URL 붙여넣기
3. import 후 **자동화 만들기 → 이 블루프린트 사용** → 종목·임계값·알림 서비스 입력 → 저장

종목을 추가/제거할 때는 **자동화 → 옵션 → 블루프린트 입력 수정** 으로 종목 체크박스만 바꾸면 됩니다.

> **알림 호환성 메모**: 두 블루프린트 모두 `notify.send_message` 서비스(HA 2024.6+ 표준)를 사용합니다. **mobile_app**(HA Companion 앱)은 자동으로 notify entity로 등록되어 검색·선택됩니다. 일부 service-only notify 통합(예 telegram_bot의 일부 모드)이 드롭다운에 안 뜨면, 그 통합용 자동화는 [docs/examples/](docs/examples/)의 raw YAML 예시를 참고하세요.

---

## 🗣️ 음성으로 물어보기

HA Assist(음성 비서)에 자동으로 등록되어, 다음과 같이 물어볼 수 있습니다:

| 이렇게 물어보면 | 이런 답을 받아요 |
|---|---|
| "코스피 지금 얼마야?" | "코스피 2,500.12, 0.5% 상승" |
| "삼성전자 시세 알려줘" | "삼성전자 7만원, 1.5% 상승" |
| "환율 얼마야?" | "USD/KRW 1,400원" |
| "오늘 가장 많이 오른 종목이 뭐야?" | 보유·관심 종목 중 변동률 1위 |
| "오늘 시장 요약해줘" | 지수·환율·총평가까지 한 번에 |
| "관심 종목 새 공시 있어?" | 최근 24시간 공시 |

`Google Assistant`, `Alexa`, `ChatGPT 음성 모드`, `Whisper 로컬` 모두 HA Assist를 통해 사용 가능합니다.

---

## ❓ 자주 묻는 질문

<details>
<summary><b>증권사 계정과 연동하나요?</b></summary>

**아니요.** 비공식 API는 보안·법적 리스크가 있어 의도적으로 빼두었습니다. 시세는 yfinance(야후 금융 공개 API), 공시는 OpenDart(금융감독원 공식)에서만 가져옵니다. 보유 종목은 직접 수량·평단가를 입력해야 평가손익이 계산됩니다.
</details>

<details>
<summary><b>유료인가요? API 키도 돈 드나요?</b></summary>

**전부 무료**입니다. yfinance·OpenDart 둘 다 무료 무제한(개인 사용 범위). 통합 자체도 MIT 라이선스 오픈소스.
</details>

<details>
<summary><b>스크래핑이라 차단 위험 있나요?</b></summary>

**없습니다.** 네이버 금융 페이지 같은 곳을 긁어오지 않습니다. yfinance는 야후 금융의 공식 차트 API, OpenDart는 정부 공식 API를 사용. 양 시장 모두 닫혀 있으면 폴링 간격이 자동으로 1분 → 10분으로 늘어나서 트래픽도 매우 적습니다.
</details>

<details>
<summary><b>장 마감 후나 주말에도 동작하나요?</b></summary>

**네.** 직전 거래일 종가를 표시합니다. 한국 공휴일·미국 공휴일 모두 자동 처리.
</details>

<details>
<summary><b>보유 종목 평가손익은 어떻게 입력하나요?</b></summary>

설정 후 **개발자 도구 → 서비스 → `kr_finance_kit.add_position`** 서비스를 호출해 종목·수량·평단가·시장(KR/US)을 입력합니다. 자동화에서도 호출 가능. 정보는 HA의 암호화 저장소에만 보관되며 외부로 나가지 않습니다.
</details>

<details>
<summary><b>차트 카드도 만들 수 있나요?</b></summary>

이 통합은 sensor만 제공하고 차트는 [apexcharts-card](https://github.com/RomRider/apexcharts-card)(별도 HACS) 또는 HA 기본 통계 카드에 연결해서 쓰시면 됩니다. 자동화 예시 폴더에 카드 yaml 예시도 포함되어 있습니다.
</details>

<details>
<summary><b>음성 비서가 통합 도구를 인식 못 하는 것 같아요</b></summary>

설정 → 음성 비서 → 사용 중인 Assistant 클릭 → **노출 항목**에서 KR Finance Kit 도구가 활성화되어 있는지 확인해주세요. 또는 LLM 기반 Assistant(예: OpenAI Conversation)인지 확인 — 단순 패턴매칭 conversation에서는 자유로운 음성쿼리가 안 됩니다.
</details>

<details>
<summary><b>옵션을 나중에 바꾸려면?</b></summary>

**설정 → 기기 및 서비스 → KR Finance Kit → 우상단 톱니바퀴(⚙) → 옵션**.
현재 값이 미리 채워져서 나오니, 종목 추가/삭제·OpenDart 키 변경만 하시고 저장하면 즉시 반영됩니다.
</details>

---

<details>
<summary>⚙️ 기술 세부사항 (개발자·고급 사용자용)</summary>

### 데이터 소스

| 데이터 | 소스 | API |
|---|---|---|
| 코스피·코스닥 | yfinance | `^KS11`, `^KQ11` |
| 나스닥·다우·S&P 500 | yfinance | `^IXIC`, `^DJI`, `^GSPC` |
| USD/KRW | yfinance | `KRW=X` |
| 한국 종목 | yfinance | `005930.KS` / `.KQ` |
| 미국 종목 | yfinance | `AAPL` |
| 암호화폐 / 환율 / 선물 | yfinance | `BTC-USD`, `EUR=X`, `GC=F` 등 (24/7) |
| 공시 + 종목명 매핑 | OpenDart | `list.json`, `corpCode.xml` |

### 만들어지는 entity

- `sensor.fi_kospi` / `_kosdaq` — 한국 지수
- `sensor.fi_nasdaq` / `_dow` / `_sp500` — 미국 지수 (`^IXIC` / `^DJI` / `^GSPC`)
- `sensor.fi_usdkrw` — 환율
- `sensor.fi_kr_<code>` — 한국 종목 가격 (attributes: `price`, `change`, `change_pct`, `asof`, `stale`)
- `sensor.fi_us_<symbol>` — 미국 종목 가격
- `sensor.fi_other_<slug>` — 암호화폐·환율·선물 (예 `_btc_usd`, `_eth_usd`, `_eur_x`, `_gc_f`). 24/7 갱신
- `sensor.fi_portfolio_*` — 6개 평가 sensor (KR/US/KRW 환산 × value/pl)
- `binary_sensor.fi_disclosure_<corp_code>` — 24h 윈도우 공시 트리거

### LLM 도구

단일 `finance_query` 함수 도구, 8개 query_type:
- `index` / `fx` / `quote` / `portfolio` / `disclosures` / `disclosure_for_ticker` / `top_movers` / `market_summary`

### 폴링 정책

- 한·미 시장 중 하나라도 열려 있음: 60초
- 양쪽 다 닫힘 (야간·주말): 600초 (자동 다이얼다운)
- 한국 공휴일: yfinance의 직전 종가 + `stale=true` 플래그

### 보안 가드

- OpenDart 키는 HA의 암호화 ConfigEntry 저장소에만 (Web UI에서 마스킹)
- 보유 종목 수량·평단가는 ConfigEntry options에 저장 (외부로 안 나감)
- NaN/inf 가드 두 layer (data + sensor)로 yfinance의 손상된 데이터 차단
- 모든 예시·테스트 픽스처는 합성 데이터

### 의존성

`yfinance>=0.2.40` 하나만. HA가 자동 설치합니다.

### 제외 사항 (의도적)

- ❌ 자동 매매 (법·약관 리스크)
- ❌ 증권사 계좌 직연동
- ❌ 차트 카드 (apexcharts-card 권장)
- ❌ 백테스팅

</details>

---

## 🔄 v0.1.34 마이그레이션 (entity_id가 `sensor.fi_*` 형식으로 단축)

v0.1.34부터 모든 entity_id가 짧은 `sensor.fi_*` 슬러그로 새로 생성됩니다 (예 `sensor.fi_kospi`, `sensor.fi_kr_005930`, `binary_sensor.fi_disclosure_<corp_code>`). 다른 finance/주식 통합과 충돌 가능성을 낮추고, 자동화·대시보드에서 한눈에 구분되도록 prefix를 `kr_finance_kit_` → `fi_` 로 단축.

⚠️ HA entity registry는 이미 등록된 entity_id를 영구 저장합니다. 즉:
- **새 설치**: 자동으로 `sensor.fi_*` 슬러그.
- **기존 설치 (v0.1.31 이하 한국어 슬러그 또는 v0.1.32~v0.1.33 `sensor.kr_finance_kit_*` 슬러그)**: 기존 entity_id 그대로 유지. 새 슬러그로 옮기려면 한 번 정리 필요.

### 정리 방법 (택일)

1. **간단 (권장)**: 설정 → 기기 및 서비스 → KR Finance Kit → ⋮ → **삭제** → 다시 추가. 보유 종목(수량·평단가)은 `kr_finance_kit.add_position` 서비스로 다시 입력 (자동화에서 호출 가능).
2. **수동**: 설정 → 기기 및 서비스 → entities → 각 entity 클릭 → 톱니바퀴 → entity ID 수정 (`sensor.kr_finance_kit_kospi` → `sensor.fi_kospi` 등). 자동화 yaml에서 참조한 entity_id도 함께 업데이트.

정리 후 블루프린트(또는 자동화)를 다시 import하면 종목 드롭다운에 새 entity_id가 깔끔하게 표시됩니다.

---

## 🐛 문제가 생기면

- 가격이 안 떠요 / 사용 불가능 상태 → HA 재시작 후 1–2분 기다리세요. 그래도 안 되면 [Issues](https://github.com/redchupa/kr_finance_kit/issues)로 로그 보내주세요.
- 옵션 화면 텍스트가 옛날 거예요 → HA 설정 → 시스템 → **다시 시작**(reload 아닌 restart)
- 종목명이 코드로만 나와요 → OpenDart 키가 비어있는 상태. 키 받아서 옵션에 입력
- 더 자세한 가이드: [docs/installation-ko.md](docs/installation-ko.md)

---

## ☕ 후원

이 통합이 도움이 되셨다면 커피 한 잔으로 응원해주세요! 🙏

<table>
  <tr>
    <td align="center">
      <b>토스</b><br/>
      <img src="https://raw.githubusercontent.com/redchupa/kr_finance_kit/main/images/toss-donation.png" alt="Toss 후원 QR" width="200"/>
    </td>
    <td align="center">
      <b>PayPal</b><br/>
      <img src="https://raw.githubusercontent.com/redchupa/kr_finance_kit/main/images/paypal-donation.png" alt="PayPal 후원 QR" width="200"/>
    </td>
  </tr>
</table>

---

<sub>🤝 버그 리포트·기능 제안: [Issues](https://github.com/redchupa/kr_finance_kit/issues) | 📦 변경 이력: [Releases](https://github.com/redchupa/kr_finance_kit/releases) | 📝 [MIT License](LICENSE)</sub>

<details>
<summary>📘 English summary</summary>

A Home Assistant HACS integration that surfaces Korean financial data — KOSPI/KOSDAQ indices, USD/KRW FX, Korean and US stock prices, holdings P/L (KRW-converted), and OpenDart corporate disclosures — as native HA sensors. Includes a `finance_query` LLM tool so you can ask "What's Samsung Electronics trading at?" through HA Voice Assist.

All data sources are free (yfinance + OpenDart's free key). No brokerage credentials. Polling auto-slows from 60s to 600s when both KR and US markets are closed.

Install via HACS → Custom repositories → `https://github.com/redchupa/kr_finance_kit`. Full setup guide at [docs/installation-en.md](docs/installation-en.md).

</details>
