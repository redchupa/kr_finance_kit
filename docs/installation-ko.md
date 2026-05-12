# 설치 가이드 (한국어)

## 1. HACS 사용자 저장소로 등록

1. HACS → 통합 → 우상단 ⋮ → **사용자 저장소**
2. URL: `https://github.com/redchupa/kr_finance_kit` 입력, 카테고리: `Integration`
3. KR Finance Kit 검색 → 다운로드 → HA 재시작

## 2. 통합 추가

설정 → 기기 및 서비스 → **통합 추가** → "KR Finance Kit"

입력값:
- **OpenDart API 키** (선택): https://opendart.fss.or.kr 에서 무료 발급
- **한국 종목 코드** (CSV): 예 `005930, 000660`
- **미국 종목 심볼** (CSV): 예 `AAPL, MSFT`
- **OpenDart 회사 고유번호** (CSV): 공시 모니터링용
- 코스피·코스닥 지수 포함 / USD/KRW 환율 포함 토글

## 3. 보안 메모

OpenDart 키는 HA 암호화 저장소에 보관됩니다. 코드/구성 파일·로그 어디에도 평문으로 노출되지 않습니다.

보유 종목 평가손익은 추후 마일스톤(M2)에서 `kr_finance_kit.add_position` 서비스로 입력합니다.
