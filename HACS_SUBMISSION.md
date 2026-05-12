# HACS Default Repository Submission

Reference notes for submitting **kr_finance_kit** to
[hacs/default](https://github.com/hacs/default) as a Korean finance HACS
integration. Mirrors the format used by `kr_component_kit`'s successful
submission.

## Pre-flight checklist

- [x] `hacs.json` at repo root with `country: ["KR"]`
- [x] `custom_components/kr_finance_kit/manifest.json` complete
- [x] LICENSE present (MIT)
- [x] README in repo root
- [x] Hassfest green on main
- [x] Pytest green on main (40 tests)
- [x] GitHub topics added (`home-assistant`, `hacs`, `hacs-integration`, etc.)
- [x] Public repo at https://github.com/redchupa/kr_finance_kit
- [ ] **Brand icons submitted to home-assistant/brands (blocker for HACS Action's last check)**

## hacs/default PR

Open against `hacs/default` adding `kr_finance_kit` to the integration
list:

```
File: integration
Add: redchupa/kr_finance_kit
```

PR title: `Add redchupa/kr_finance_kit`

PR body template:
```
- Repository: https://github.com/redchupa/kr_finance_kit
- Category: integration
- Description: Home Assistant integration exposing Korean financial data
  (KOSPI/KOSDAQ, USD/KRW, holdings P/L, OpenDart disclosures) as native
  sensors with an LLM tool for voice queries. Free yfinance + OpenDart
  data; no scraping, no brokerage credentials.
```

## home-assistant/brands PR

Required for the HA UI to show the integration's icon. Files to add:

- `custom_integrations/kr_finance_kit/icon.png` — 256×256 transparent PNG
- `custom_integrations/kr_finance_kit/icon@2x.png` — 512×512
- `custom_integrations/kr_finance_kit/logo.png` — wordmark, 256×256+

Mirror the `kr_component_kit` brand PR pattern. Generated icons live under
`custom_components/kr_finance_kit/brand/` once created.

## Versioning

This repo follows semver. `manifest.json:version` MUST be bumped before
each HACS-tagged release. The release process:

1. Bump version in `manifest.json`
2. `git tag v<X.Y.Z> && git push --tags`
3. Create GitHub Release with changelog
4. HACS picks up the release automatically
