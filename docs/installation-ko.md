# 설치 가이드 (한국어)

## 1. HACS 사용자 저장소로 등록

1. HACS → 통합 → 우상단 ⋮ → **사용자 저장소**
2. URL: `https://github.com/redchupa/kr_finance_kit` 입력, 카테고리: `Integration`
3. Finance Kit 검색 → 다운로드 → HA 재시작

## 2. 통합 추가

설정 → 기기 및 서비스 → **통합 추가** → "Finance Kit"

입력값:
- **OpenDart API 키** (선택): https://opendart.fss.or.kr 에서 무료 발급
- **한국 종목 코드** (CSV): 예 `005930, 000660`
- **미국 종목 심볼** (CSV): 예 `AAPL, MSFT`
- **OpenDart 회사 고유번호** (CSV): 공시 모니터링용
- 코스피·코스닥 지수 포함 / USD/KRW 환율 포함 토글

## 3. 보안 메모

OpenDart 키는 암호화하여 HA 설정 항목에 저장합니다. 복호화 키는 같은 HA의 비공개 저장소에 있으므로 HA 구성 디렉터리와 백업에 접근할 수 있는 사람을 제한하세요.

보유 종목 평가손익은 추후 마일스톤(M2)에서 `kr_finance_kit.add_position` 서비스로 입력합니다.
