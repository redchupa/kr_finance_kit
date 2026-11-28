# Installation (English)

## 1. Install from HACS

Finance Kit is in the default HACS list, so you don't need to add a custom repository.

1. Open HACS and search "Finance Kit"
2. Download → restart HA

## 2. Add the integration

Settings → Devices & services → **Add integration** → "Finance Kit"

Inputs:
- **OpenDart API key** (optional): get one free at https://opendart.fss.or.kr
- **KR ticker codes** (CSV): e.g. `005930, 000660`
- **US ticker symbols** (CSV): e.g. `AAPL, MSFT`
- **OpenDart corp_codes** (CSV): for disclosure monitoring
- Toggles for indices and FX

## 3. Security note

Finance Kit encrypts the OpenDart key before saving the config entry. The decryption key lives in private storage on the same HA instance. Restrict access to the configuration directory and backups.

Holdings (quantity / average price) are added later in M2 via the `kr_finance_kit.add_position` service.
