# kr_finance_kit — 한국 금융 HACS 통합

## 1. 목적

> Home Assistant에서 **한국 주식·환율·OpenDart 공시·미국 주식**을 네이티브 센서로 노출하는 통합. 자동화 트리거·LLM 음성쿼리 가능.

**왜?**
- 본인이 이미 `daily_market.py`, `/일일브리핑` 스킬, `auto_blog/daily_market.py` 등에서 OpenDart·yfinance·Naver 금융을 호출 중 — **데이터 파이프라인 검증 완료**.
- 한국 금융 데이터를 HA 자동화에 통합할 수 있는 HACS 통합 사실상 부재.
- `kr_component_kit`은 의도적으로 "공공·생활 서비스"에 한정 — 금융은 별 레포가 맞음.
- 본인 HA 자동화 133개에 즉시 편입 가능 (예: "특정 종목 5% 하락 시 텔레그램 알림").
- LLM tool 패턴 (`kr_component_kit`의 자연어 쿼리)을 그대로 적용 → 음성으로 "지금 코스피 어때?" 가능.

## 2. 타겟 사용자

- 한국 주식 투자하는 HA 사용자
- "장 마감 직후 자동화 트리거" 같은 시나리오를 원하는 트레이더
- 음성 비서(VPE, ChatGPT, Claude)로 시세 묻고 싶은 사람

## 3. 범위

**IN (v1)**
- ✅ 코스피·코스닥·KRW/USD 환율 실시간 센서
- ✅ 종목별 시세 센서 (티커 입력 → sensor)
- ✅ 미국 주식 (yfinance — 같은 코드 경로)
- ✅ 보유 종목 평가손익 — 수량·평단가 config로 입력
- ✅ OpenDart 공시 binary_sensor — 관심 종목에 신규 공시 시 ON
- ✅ LLM tool: "보유 종목 시가총액 합 알려줘" / "삼성전자 지금 얼마?"
- ✅ Config Flow UI (HACS 표준)

**OUT (v1)**
- ❌ 자동 매매 (법·증권사 약관 이슈)
- ❌ 증권사 계좌 직연동 (비공식 API 의존성 + 보안 리스크)
- ❌ 차트 카드 (apexcharts-card 사용 권장, redchupa-cards에서 wrapper 제공 가능)
- ❌ 백테스팅 / 시뮬레이션

## 4. 아키텍처

```
custom_components/kr_finance_kit/
├── __init__.py           # async_setup_entry
├── manifest.json         # domain, version, requirements (yfinance, beautifulsoup4)
├── config_flow.py        # UI 설정
├── const.py
├── coordinator.py        # DataUpdateCoordinator (틱·환율·공시)
├── sensor.py             # 가격·평가손익 센서
├── binary_sensor.py      # 공시 발생 트리거
├── llm_tool.py           # 자연어 쿼리 (kr_component_kit 패턴)
├── services.yaml         # action: refresh_now, add_position
├── translations/
│   ├── ko.json
│   └── en.json
└── api/
    ├── naver_finance.py  # 코스피·코스닥·환율 (Naver 금융 공개 페이지)
    ├── opendart.py       # 공시 (free key)
    └── yfinance_wrap.py  # 미국 + ETF
```

데이터 소스 (모두 무료):
| 데이터 | 소스 | 인증 |
|---|---|---|
| KOSPI/KOSDAQ 지수 | Naver 금융 공개 페이지 | 없음 (스크래핑) |
| 종목 시세 (한국) | Naver 금융 또는 KRX 공개 | 없음 |
| USD/KRW | Naver 환율 | 없음 |
| 미국 주식 | yfinance | 없음 |
| 공시 | OpenDart (`data.opendart.fss.or.kr`) | 무료 키 |

## 5. 파일 구조 (v1 골격)

```
kr_finance_kit/
├── README.md                 # 한·영
├── LICENSE                   # MIT
├── PLAN.md
├── CLAUDE.md
├── hacs.json                 # HACS Integration 메타
├── .gitignore
├── .env.example              # OPENDART_API_KEY (개발용, 커밋 X)
├── custom_components/
│   └── kr_finance_kit/       # (위 §4 구조)
├── tests/
│   ├── fixtures/
│   │   ├── opendart_sample.json    # 합성 공시 응답
│   │   └── naver_sample.html       # 합성 페이지
│   └── test_*.py
├── docs/
│   ├── installation-ko.md
│   ├── installation-en.md
│   └── examples/
│       └── automation-examples.yaml   # 종목 알림 등 (티커 placeholder)
└── .github/workflows/
    ├── test.yml
    └── hassfest.yml          # HA 공식 검증 (kr_component_kit 패턴)
```

## 6. 마일스톤

### M0 — Bootstrap ✅
- [x] 통합 골격 (manifest, config_flow, coordinator skeleton)
- [x] `kr_component_kit` 코드 구조 참고
- [x] hassfest.yml + test.yml CI
- [x] README 초안

### M1 — 시세 센서 ✅
- [x] yfinance_wrap.py — KOSPI/KOSDAQ + 환율 + 한국·미국 종목 시세
  - (PLAN 원안의 naver_finance.py 스크래핑은 `daily_market.py` 자산이 이미 yfinance로 검증되어 있어 일원화 — 안정성·스크래핑 윤리 가드 모두 향상)
- [x] sensor.py — 종목별 sensor + 지수/환율 센서
- [x] Config Flow UI — 멀티스텝(tickers → disclosures) + OptionsFlow
- [x] tests: 합성 fixture로 파서/정규화 검증

### M2 — 보유 종목 + 공시 ✅
- [x] sensor.py — KR/US/KRW 환산 평가손익 (6개 portfolio 센서)
- [x] opendart.py — 신규 공시 폴링 (aiohttp + HA session)
- [x] binary_sensor.py — 공시 발생 시 ON, attributes에 제목/링크/url
- [x] services.yaml: `refresh_now` + `add_position` + `remove_position` (entry.options에 저장)
- [x] 한·미 장 운영시간 인식 → 장외 폴링 1분 → 10분 다이얼다운
- [x] OpenDart stock_code → corp_code 자동 변환 (`company.json` 활용)

### M3 — LLM tool + 릴리스 (진행 중)
- [x] llm_tool.py — pure dispatch 분리, 8개 query_type
  - index, fx, quote, portfolio, disclosures, disclosure_for_ticker, top_movers, market_summary
- [x] yfinance stale-day fallback (한국 공휴일 시 단봉 → `stale: true` 플래그)
- [x] docs/ 한·영 (installation + examples)
- [x] HACS_SUBMISSION.md (default repo PR + brands PR 준비물)
- [x] examples/automation-examples.yaml + daily-summary-automation.yaml
- [x] README 후원 섹션
- [x] GitHub public repo 생성 + push → https://github.com/redchupa/kr_finance_kit
- [x] CI 그린: Hassfest ✓, Tests ✓ (40/40), HACS Action 7/8 ✓
- [x] HACS topics 추가
- [ ] **남은 외부 작업 (사용자 결정)**:
  - [ ] home-assistant/brands PR (icon.png 256×256, logo.png) — HACS의 마지막 1/8 check 해제
  - [ ] hacs/default PR (HACS_SUBMISSION.md 본문 그대로 사용)
  - [ ] 첫 GitHub Release (manifest.json `0.0.1` → `0.1.0` bump + 태그)

## 7. 무료/보안 가드 (본 레포 특화)

### API 키 처리
- OpenDart 키: **반드시 Config Flow에서 입력받고 HA 암호화 저장소(`async_save_credentials` 패턴)에 보관**.
- 코드/README/예시에 OpenDart 키 평문 X.
- `.env.example`에만 `OPENDART_API_KEY=` (값 비움).

### 보유 종목 정보
- 본인 실보유 종목 리스트 X.
- 예시·테스트 픽스처는 시총 상위 일반 종목(`005930`, `000660`, `005380`)으로 합성.
- README 스크린샷의 평가손익 금액은 합성 (예: "1,234,567원").

### 스크래핑 윤리
- Naver 금융 페이지 스크래핑은 robots.txt 준수, User-Agent 명시, rate limit (1초당 1회 등).
- 과도한 요청으로 IP 차단 위험 → coordinator에 jitter 추가.
- README에 "Naver 금융 공개 페이지를 사용하며, 폭주 시 차단 가능" 면책.

### 증권사 API 비-사용
- 본인이 쓰는 증권사 계정 정보 / 키 / 비공식 API URL 절대 포함 X.
- 보유 종목은 **수동 입력 only** (자동 계좌 연동 v1 제외).

### 후원 메타
- HA device entry에 후원 메타 박기:
  ```python
  DeviceInfo(
      identifiers={(DOMAIN, entry_id)},
      manufacturer="우*만",
      model="토스 1000-1261-7813",
      sw_version="커피 한잔은 사랑입니다",
      name="KR Finance Kit",
  )
  ```

## 8. 본인 자산 참조 (재활용 가능 경로)

| 자산 | 위치 | 어떻게 쓰나 |
|---|---|---|
| 일일 시장 수집 | `tistory_to_wordpress/auto_blog/daily_market.py` | Naver 금융 파싱 패턴 |
| chrome 수집기 | `~/.claude/agents/daily-market-report:chrome-collector` | KOSPI/KOSDAQ 추출 셀렉터 |
| naver 수집기 | `~/.claude/agents/daily-market-report:naver-collector` | 뉴스/이슈 패턴 |
| 일일브리핑 스킬 | `~/.claude/skills/일일브리핑/` | 데이터 흐름 참고 |
| kr_component_kit | `github_auto_development/kr_component_kit/custom_components/kr_component_kit/` | Config Flow + LLM tool 패턴 |
| AI Task 쿼터 가드 | `homeassistant_mcp/memory/ai_task_quota_guard.md` | coordinator의 polling 가드 패턴 |
| 한국 시간 처리 | `homeassistant_mcp/memory/ha_template_datetime_naive_aware.md` | 장 마감 시각 처리 |

> **재활용 워크플로**: 코드 카피 시 본인 종목 코드·계좌·금액 즉시 삭제 후 일반화.

## 9. 수락 기준 (v1.0 DoD)

- [ ] HACS Custom repository로 설치 → Config Flow에서 OpenDart 키 + 티커 3개 입력 → 5분 안에 sensor 동작
- [ ] `sensor.kr_finance_kit_kospi`, `sensor.kr_finance_kit_005930` 등 정상 갱신
- [ ] `binary_sensor.kr_finance_kit_005930_disclosure` — OpenDart 공시 신규 시 ON
- [ ] LLM tool: "삼성전자 지금 얼마?" 답변 정상
- [ ] hassfest CI 그린
- [ ] tests/ 합성 fixture로 파서·coordinator 검증
- [ ] 보안 grep: OpenDart 키 / 본인 종목·수량·평단가 / 192.168 / redchupa 0건

## 10. 다음 세션 시작 프롬프트

```
이 폴더는 kr_finance_kit (한국 금융 HACS 통합) 프로젝트입니다.
PLAN.md, CLAUDE.md, ../MASTER_PLAN.md 를 먼저 읽으세요.

작업: M0 (Bootstrap) 부터 진행.
1. ../kr_component_kit/custom_components/kr_component_kit/ 구조를 참고하여 동일한 패턴으로 골격 생성
   (manifest.json, config_flow.py, coordinator.py, sensor.py 스켈레톤)
2. hacs.json (HACS Integration 타입)
3. tests/fixtures/ 에 합성 OpenDart 응답 + 합성 Naver 페이지
4. .github/workflows/hassfest.yml + test.yml
5. README 초안 (한·영)

PLAN.md §7 보안 가드 + MASTER_PLAN.md 공통 규칙 준수.
특히: OpenDart 키 / 본인 보유 종목 / 증권사 계정 / IP / 호스트 절대 코드·README 포함 금지.
끝나면 진행사항 요약 + 다음 단계 제안.
```
