# Installation (English)

## 1. Add as a HACS custom repository

1. HACS → Integrations → top-right menu → **Custom repositories**
2. URL: `https://github.com/redchupa/kr_finance_kit`, category: `Integration`
3. Search "KR Finance Kit" → download → restart HA

## 2. Add the integration

Settings → Devices & services → **Add integration** → "KR Finance Kit"

Inputs:
- **OpenDart API key** (optional): get one free at https://opendart.fss.or.kr
- **KR ticker codes** (CSV): e.g. `005930, 000660`
- **US ticker symbols** (CSV): e.g. `AAPL, MSFT`
- **OpenDart corp_codes** (CSV): for disclosure monitoring
- Toggles for indices and FX

## 3. Security note

The OpenDart key is kept in Home Assistant's encrypted storage — it never appears in source files, fixtures, or logs.

Holdings (quantity / average price) are added later in M2 via the `kr_finance_kit.add_position` service.
