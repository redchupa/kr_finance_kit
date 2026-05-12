# Claude 세션 부트스트랩 — kr_finance_kit

> 이 파일은 새 Claude Code 세션이 이 프로젝트 폴더를 열 때 자동으로 읽는 컨텍스트입니다.

## 🔒 최상위 규칙 (위반 시 즉시 작업 중단)

레포 어디에도 다음을 평문으로 포함하지 말 것:
- **OpenDart API 키** (반드시 Config Flow + HA 암호화 저장만)
- 증권사 계정 / 비공식 API URL / 세션 쿠키
- **본인 보유 종목·수량·평단가·평가손익** (예시·테스트 픽스처 포함)
- 사설 IP, 본인 HA URL, 본인 도메인
- 가족 실명
- 본인이 즐겨찾는 종목 코드를 README 예시에 그대로 박지 말 것 (일반화: 시총 상위 임의 종목)

대신: `OPENDART_API_KEY=` 빈 값, `your_ticker`, `005930` 같은 공개 종목 예시.

**예외 (의도적 공개)**: 후원 메타 (HA device entry + README)

## 프로젝트 한 줄

한국 주식·환율·OpenDart 공시·미국 주식을 HA 센서로 노출하는 HACS 통합. Config Flow + LLM tool.

## 작업 시작 시

1. **`PLAN.md` 정독** — §7 보안 가드 (API 키 처리, 보유 종목 비-노출)
2. **`../MASTER_PLAN.md` 정독** — 공통 규칙
3. **`../kr_component_kit/custom_components/kr_component_kit/`** 구조 참고 (Config Flow + LLM tool 패턴)
4. 현재 마일스톤(M0~M3) 확인

## 코드 원칙

- Python 3.12+
- HA custom_component 표준 구조 (manifest.json, config_flow, coordinator, sensor, binary_sensor, calendar)
- 무료 데이터 소스만: Naver 금융 공개 페이지, yfinance, OpenDart 무료 키
- 스크래핑 윤리: rate limit, User-Agent 명시, jitter
- AI 호출 인라인 유지 (`feedback_ai_inline_in_automation.md`)
- 가독성 > 최적화

## 본인 자산 (재활용 워크플로)

PLAN.md §8 참고. 본인 일일브리핑 스킬/`daily_market.py`의 파싱 로직만 추출하되 본인 보유 종목·금액·예시 즉시 제거.

## 발행 전 체크리스트

```bash
grep -rE "OPENDART_API_KEY=[^\s]+|192\.168\.|redchupa|jerry|하린|예린|제리|WooRin" . --exclude-dir=__pycache__
```

OpenDart 키 / 본인 보유 종목 코드·수량 어디에도 없는지 검증.

## 다음 단계

PLAN.md §10 "다음 세션 시작 프롬프트" 를 첫 메시지로 사용.
