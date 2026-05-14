# Release checklist — kr_finance_kit

> 본 레포는 보안 가드에 따라 **`your-github-username`** placeholder로 출시됩니다.
> 이 체크리스트는 본인 fork를 release할 때 placeholder를 안전하게
> 치환하고 HACS / hassfest CI를 통과시키는 절차입니다.

---

## 1. GitHub username placeholder 치환 (모든 fork 공통)

다음 6개 파일에서 `your-github-username`을 본인 GitHub 핸들로 일괄 치환:

```bash
git grep -l "your-github-username"
# Expected matches:
#   custom_components/kr_finance_kit/manifest.json   (codeowners + documentation + issue_tracker)
#   README.md                                        (배지 2개)
#   docs/installation-ko.md
#   docs/installation-en.md
#   HACS_SUBMISSION.md                               (3개 — repo URL + PR title + PR body)
#   LICENSE                                          (Copyright)
```

PowerShell 일괄 치환:

```powershell
$me = "<your-github-handle>"   # ← 본인 GitHub 핸들로 교체 후 따옴표만 남기기
Get-ChildItem -Recurse -Include "*.md","*.json","LICENSE" |
    ForEach-Object { (Get-Content $_ -Raw).Replace("your-github-username", $me) |
        Set-Content $_ -Encoding UTF8 -NoNewline }
```

검증:

```bash
git grep "your-github-username"   # → 결과 없어야 함
```

> ⚠️ Release 브랜치에서만 이 치환을 적용하고, `main`은 placeholder 상태를
> 유지하는 워크플로를 권장합니다. CI(`test.yml`)의 privacy grep이 본인
> 핸들을 잡을 경우 release 브랜치에서만 grep 패턴 화이트리스트에
> 추가하거나 `if: github.ref != 'refs/heads/release/*'` 조건으로 우회.

## 2. Version bump (manifest + 태그)

```bash
# manifest.json:version은 PEP 440. SemVer + alpha/beta 모두 OK.
# 예: 0.1.3 → 0.2.0
```

CHANGELOG 작성이 의무는 아니지만, GitHub Release notes에 반영할 한
줄~문단을 미리 준비하면 좋습니다.

## 3. 로컬 검증

```bash
# 단위 테스트
python -m pytest -q

# 코드 품질 (선택 — kr_finance_kit은 아직 ruff 설정 미포함)
# 추가하려면 pyproject.toml + [tool.ruff] 섹션 (kr_baby_kit 패턴 참고)

# 보안 grep — 본인 GitHub 핸들이 placeholder 자리에 들어갔는지 확인
# (main 브랜치는 0건이어야 하고, release 브랜치는 본인 핸들만 존재)
grep -rE "your-github-username" --exclude-dir=.git --exclude-dir=__pycache__ . || echo "ok"

# OpenDart 키 / 본인 종목 정보 유출 확인
grep -rE "OPENDART_API_KEY=[A-Za-z0-9]{30,}" --exclude-dir=.git . && echo "LEAK" || echo "clean"
```

## 4. CI 통과 확인

```bash
git push origin release/v<version>
```

- **hassfest** — manifest.json 구조 검증. `@<github-handle>` 형식만 보고
  실제 GitHub API 호출은 하지 않으므로, format이 valid한 핸들이면 통과.
- **HACS validation** — `hacs.json` + `manifest.json` + `README.md` 존재 + 도메인 일치.
- **pytest** — Python 3.11/3.12/3.13 매트릭스.

CI가 깨질 가능성이 가장 높은 곳:
- privacy grep이 본인 핸들을 잡는 경우 → release 브랜치 우회 조건 추가
- HACS Action의 brands 검증 → `home-assistant/brands` PR이 머지될 때까지
  7/8 통과로 끝나는 게 정상. blocker 아님.

## 5. Git tag + GitHub Release

```bash
git tag -a v<version> -m "Release v<version> — <one-liner>"
git push origin v<version>
# Then on GitHub: Releases → Draft new release → pick the tag
```

릴리스 노트는 의미 있는 변경만 짧게 (예: "M2 보유 종목 + OpenDart 공시
추가"). HACS Custom Repository 사용자에게 자동 노출됩니다.

## 6. HACS Default Repository PR (선택)

본인 fork를 [hacs/default](https://github.com/hacs/default)에 추가하면
모든 HACS 사용자가 검색해서 설치 가능. 절차는
[`HACS_SUBMISSION.md`](../HACS_SUBMISSION.md) 본문 그대로 사용:

1. `home-assistant/brands` PR (icon.png 256×256, logo.png 512×128 권장)
   머지 후
2. `hacs/default` PR (PR body는 `HACS_SUBMISSION.md`의 "hacs/default PR" 섹션)

`home-assistant/brands`가 먼저 머지되어야 HACS Action의 마지막 1/8 check가
통과합니다.

## 7. (선택) ruff/lint 설정 추가

kr_baby_kit / kidsnote-diary-suite와 일관 패턴으로 ruff를 추가하려면
`pyproject.toml`에:

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "W"]
ignore = ["E501"]
```

그리고 `.github/workflows/lint.yml` 추가. 현재 v0.1.3까지는 lint CI 없음.

---

## 부록: placeholder 모드를 main에 유지하는 이유

- **GitHub username**: 본인의 보안 가드(`CLAUDE.md` §보안 가드)가 본인
  핸들 노출을 금지. main이 placeholder이면 fork 사용자나 다른 트레이더도
  본인 fork에 자기 username만 채워 사용 가능. 이미 본인이 publish한
  GitHub repo URL은 PLAN.md의 진행 기록(line 127)에만 남아 있으며
  내부 문서이므로 외부 검색에 노출되지 않습니다.
- **HACS_SUBMISSION.md placeholder**: 본인 fork를 hacs/default에 PR할 때
  본문에 본인 핸들을 직접 적어야 하므로, 이 문서도 release 브랜치에서
  한 번에 치환되어야 함을 가이드합니다.
