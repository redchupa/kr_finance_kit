# KR Finance Kit

English · **[한국어](README.md)**

> Korean and US equities, FX, crypto, and OpenDart disclosures — all surfaced as native Home Assistant sensors.
> Free APIs only, no brokerage credentials, voice-assist friendly.

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-FF8C00?style=flat-square&logo=homeassistantcommunitystore&logoColor=white)](https://hacs.xyz)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.6%2B-03A9F4?style=flat-square&logo=home-assistant&logoColor=white)](https://www.home-assistant.io)
[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org)

[![Validate](https://img.shields.io/github/actions/workflow/status/redchupa/kr_finance_kit/validate.yml?label=validate&style=flat-square&logo=github)](https://github.com/redchupa/kr_finance_kit/actions/workflows/validate.yml)
[![Tests](https://img.shields.io/github/actions/workflow/status/redchupa/kr_finance_kit/test.yml?label=tests&style=flat-square&logo=github)](https://github.com/redchupa/kr_finance_kit/actions/workflows/test.yml)
[![Data: yfinance](https://img.shields.io/badge/data-yfinance-7B1FA2?style=flat-square&logo=yahoo&logoColor=white)](https://github.com/ranaroussi/yfinance)
[![Disclosures: OpenDart](https://img.shields.io/badge/disclosures-OpenDart-E53935?style=flat-square)](https://opendart.fss.or.kr)
[![Made for HA](https://img.shields.io/badge/Made%20for-Home%20Assistant-18BCF2?style=flat-square&logo=home-assistant&logoColor=white)](https://www.home-assistant.io)

[Releases](https://github.com/redchupa/kr_finance_kit/releases)

---

## What you can do

- ☕ KOSPI, your tickers, FX, Bitcoin — all on the living-room wall panel
- 📉 Push the moment a holding moves ±5% from your average cost
- ⏱️ Trigger on "moved ±2% in the last 30 minutes"
- 🗣️ "Hey Google, what's Samsung trading at?"
- 🔔 OpenDart new-disclosure alerts (category-filtered)
- 📊 Daily summary auto-sent right after market close

All on **free APIs** (yfinance + OpenDart free key), no brokerage account needed.

---

## 5-minute install

### Prerequisites
- Home Assistant + [HACS](https://hacs.xyz)

### Step 1 · Add HACS repository
1. HACS → ⋮ → **Custom repositories**
2. URL `https://github.com/redchupa/kr_finance_kit`, Type `Integration` → Add

### Step 2 · Download
1. Search **KR Finance Kit** in HACS → Download
2. **Restart Home Assistant fully** (Restart, not Reload)

### Step 3 · Add integration
**Settings → Devices & services → + Add integration → "KR Finance Kit"**

---

## Option screen at a glance (v0.1.52)

Each field label carries a paste-ready example after the colon.

| Option | What it does |
|---|---|
| OpenDart API key | (optional) Unlocks disclosure alerts + auto company-name labels |
| Korean ticker codes | CSV. 6-digit = KOSPI, `.KQ` suffix = KOSDAQ |
| US ticker symbols | CSV. `AAPL:Apple` for explicit friendly name (else yfinance longName auto-fills) |
| Crypto / FX / Futures | Yahoo ticker form (`BTC-USD`, `EUR=X`, `GC=F`). 24/7 fetch |
| Include KOSPI/KOSDAQ indices | Toggle (default ☑) |
| Include NASDAQ/Dow/S&P 500 indices | Toggle (default ☑) |
| Include global indices | Nikkei / Hang Seng / FTSE / DAX (default ☐) |
| Include USD/KRW FX | Toggle (default ☑) |
| Include detailed attributes | 52w high/low, 200d avg, dividend, PE etc. (extra traffic, default ☐) |
| Convert USD assets to KRW | Adds `price_krw` to USD QuoteSensors (default ☐) |
| Portfolio P/L alert threshold % | 0 disables. Set 5 → binary_sensor flips when cost-basis P/L crosses ±5% |
| Disclosure category filter | Multi-select from 10 OpenDart pblntf_ty codes. Empty = all |

---

## Generated sensors

### Market indicators (opt-in toggles)
- `sensor.fi_kospi` / `sensor.fi_kosdaq` — Korean indices
- `sensor.fi_nasdaq` / `_dow` / `_sp500` — US indices
- `sensor.fi_nikkei` / `_hangseng` / `_ftse` / `_dax` — global indices
- `sensor.fi_usdkrw` — USD/KRW FX

### Ticker quotes
- `sensor.fi_kr_<6digit>` — Korean (e.g. `_kr_005930`)
- `sensor.fi_us_<symbol>` — US (e.g. `_us_aapl`)
- `sensor.fi_other_<slug>` — Crypto / FX / futures (24/7, e.g. `_other_btc_usd`)

### Quote-sensor attributes
- Default: `price`, `change`, `change_pct` (vs. previous close), `prev_close`, `asof`, `stale`
- Detailed-attrs ON: `fifty_two_week_high/low`, `fifty/two_hundred_day_average`, day high/low/volume, `market_state`, `currency`, `quote_type`, `long_name`; equities also `dividend_*`, `forward_pe`, `trailing_pe`
- KRW-convert ON (USD assets only): `price_krw`
- Per CSV minute entry: `change_pct_<N>min` (e.g. config `15, 30, 60` → 3 attributes)

### Portfolio (after adding positions via service)
- `sensor.fi_portfolio_kr_value` / `_kr_pl` / `_us_value` / `_us_pl` / `_krw_total` / `_krw_pl`
- `binary_sensor.fi_portfolio_pl_alert` — ON when cost-basis P/L crosses ±threshold

### Disclosures (OpenDart key + KR tickers)
- `binary_sensor.fi_disclosure_<corp_code>` — 24h window, device label is the corp_name (e.g. `삼성전자`)

### HA event bus (no toggle, always fires)
- `kr_finance_kit_kr_market_closed` — fires on KR market close edge
- `kr_finance_kit_us_market_closed` — fires on US market close edge

---

## Recording holdings (service / action)

Holdings (quantity + average cost) are entered as a **service call**, not on the option form, so they stay in HA's encrypted store.

### 1. Where to enter them

**Settings → Developer Tools → Actions tab** → type `kr_finance_kit.add_position` in the search box → the form appears.

![Add position dialog](docs/screenshots/add_position.png)

> HA 2024.8+ renamed the old "Services" tab to "Actions". Same screen — only the label moved.

### 2. Fields

| UI label | Key | Example | Notes |
|---|---|---|---|
| Ticker / symbol | `ticker` | `005930` / `AAPL` | KR = 6-digit code (KOSDAQ adds `.KQ`), US = symbol |
| Quantity | `quantity` | `10` | Share count |
| **Average price** | `avg_price` | KR `60000` (KRW) · US `180.5` (USD) | **Native market currency** — do NOT pre-convert |
| Market | `market` | `KR` or `US` | Radio button |

> ⚠ **Crypto / FX / futures (BTC-USD, EUR=X, GC=F …) are price-only.** Portfolio tracking isn't supported for them — the `market` radio only offers KR / US. Don't try to enter a Bitcoin position.

> 💱 **Auto-conversion** — enter KR positions in won, US positions in dollars. The integration pulls USD/KRW itself and rolls everything into `sensor.fi_portfolio_krw_total` / `sensor.fi_portfolio_krw_pl`. Pre-converting will double-count.

After saving, the six portfolio sensors (`sensor.fi_portfolio_*`) and the P/L alert binary_sensor turn on automatically.

### 3. Removing

In the same screen pick `kr_finance_kit.remove_position` → enter `ticker` + `market` → run.

### 4. Bulk-import via YAML (optional)

If you want to record many tickers at once, click "Go to YAML mode" on the Actions tab:

```yaml
action: kr_finance_kit.add_position
data:
  ticker: "005930"
  quantity: 10
  avg_price: 60000
  market: KR
```

Run the action once per ticker. Wrap them in a startup automation to repopulate on HA boot if you prefer.

---

## Three automation blueprints

Register many tickers in the integration, then check which ones each blueprint should watch. No need to recreate automations when the watch list changes.

### 1. Price change alert (vs. previous close)
[![import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fredchupa%2Fkr_finance_kit%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fkr_finance_kit%2Fprice_change_alert.yaml)

Triggers off `change_pct`. Inputs: tickers · drop threshold · rise threshold · notify target.

### 2. Short-window alert (user-defined minutes)
[![import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fredchupa%2Fkr_finance_kit%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fkr_finance_kit%2Fshort_window_alert.yaml)

v0.1.53+: the sensor exposes **1, 5, 15, 30, 60, 90, 120, 180 minute** attributes out of the box (no option to configure). The blueprint's number input accepts any of those values; per-ticker different minutes = one blueprint instance per ticker.

> 📥 **Warm-up after import** — the first alert needs one window's worth of samples
> ⚠️ **HA restart caveat** — N-min window is None for ~N minutes after restart (memory-only buffer)

### 3. Daily market summary
[![import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fredchupa%2Fkr_finance_kit%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fkr_finance_kit%2Fdaily_summary.yaml)

At a configurable time (defaults to KR market close, 15:30 KST), bundles indices + FX + tickers + portfolio totals into one message.

### Notify compatibility
All three use `notify.send_message` (HA 2024.6+ standard). mobile_app auto-works. Service-only notify integrations (some telegram_bot modes) → see raw YAML in [docs/examples/](docs/examples/).

---

## 📊 Ready-made dashboard

An eight-section sample dashboard — portfolio summary · indices & FX · KR/US holdings · OpenDart disclosures · 7-day price trends · quick links.

[![dashboard.yaml](https://img.shields.io/badge/copy-docs%2Fexamples%2Fdashboard.yaml-blue?logo=homeassistant)](docs/examples/dashboard.yaml)

### How to use

1. Copy the view block from [docs/examples/dashboard.yaml](docs/examples/dashboard.yaml)
2. HA → Settings → Dashboards → ⋮ Edit → ⋮ **Raw configuration editor**
3. Paste under `views:` → Save
4. In sections 4 / 5 / 6 replace the placeholder tickers (e.g. `sensor.fi_kr_005930`) with your own

> All entity refs use the `sensor.fi_*` / `binary_sensor.fi_*` form. Works out of the box on v0.1.54+ after the migration runs.

### Sections at a glance

| Section | Card type | Entities |
|---|---|---|
| 1. Hero | markdown | total value / P/L via template + index summary |
| 2. Portfolio | tile × 7 | KRW totals + per-country value/P/L + alert |
| 3. Indices & FX | tile × 6 | KOSPI / KOSDAQ / USDKRW / NASDAQ / DOW / SP500 |
| 4. 🇰🇷 KR holdings | tile × N | your tickers (placeholders) |
| 5. 🇺🇸 US holdings | tile × N | your tickers (placeholders) |
| 6. Disclosures | tile × N | OpenDart binary_sensors |
| 7. Price trends | history-graph × 3 | 7 days / 168 hours |
| 8. Quick links | markdown | add position · integration options · automations |

---

## Hand-rolled automations (yaml)

### Portfolio P/L alert
```yaml
trigger:
  - platform: state
    entity_id: binary_sensor.fi_portfolio_pl_alert
    to: "on"
action:
  - service: notify.mobile_app_my_phone
    data:
      title: "Portfolio alert"
      message: >
        P/L {{ state_attr('binary_sensor.fi_portfolio_pl_alert', 'current_pl_pct') }}%
        crossed ±{{ state_attr('binary_sensor.fi_portfolio_pl_alert', 'threshold_pct') }}%
```

### Right after KR market close
```yaml
trigger:
  - platform: event
    event_type: kr_finance_kit_kr_market_closed
action:
  - service: notify.notify
    data:
      message: "KOSPI close {{ states('sensor.fi_kospi') }}"
```

More examples: [docs/examples/](docs/examples/)

---

## Voice assist

Auto-registers a `finance_query` LLM tool with HA Assist. Eight query types:
- index / fx / quote / portfolio / disclosures / disclosure_for_ticker / top_movers / market_summary

Try:
- "What's KOSPI at?"
- "Samsung Electronics quote"
- "Today's biggest gainer?"
- "Summarize the market"
- "Any new disclosures on my watchlist?"

Works with Google Assistant / Alexa / ChatGPT voice / local Whisper — any LLM-backed HA Assist setup.

---

## FAQ

<details>
<summary><b>Does it touch a brokerage account?</b></summary>

**No.** Unofficial brokerage APIs carry security and TOS risk and are deliberately excluded. yfinance (Yahoo Finance public chart) + OpenDart (FSS official) + your own avg_price/quantity entries.
</details>

<details>
<summary><b>Is it free?</b></summary>

Yes — yfinance and OpenDart are both free with personal-use limits. Integration itself is MIT.
</details>

<details>
<summary><b>Does it work after-hours / on weekends?</b></summary>

Shows the last available close. KR and US holidays auto-detected. Crypto + FX update 24/7.
</details>

<details>
<summary><b>Why is the short-window value None right after HA restart?</b></summary>

The ring buffer is memory-only by design. An N-minute window stays None for ~N minutes — then resumes normally. 60-min window = ~1 hour warm-up.
</details>

<details>
<summary><b>How do I change options later?</b></summary>

Settings → Devices & services → KR Finance Kit → ⚙ Options. Saving auto-reloads the integration.
</details>

<details>
<summary><b>Charts?</b></summary>

Sensors only. Pipe into [apexcharts-card](https://github.com/RomRider/apexcharts-card) (separate HACS) or HA's built-in statistics card.
</details>

---

<details>
<summary>⚙️ Technical details</summary>

### Data sources
| Data | Source | yfinance ticker |
|---|---|---|
| KOSPI / KOSDAQ | yfinance | `^KS11`, `^KQ11` |
| NASDAQ / Dow / S&P 500 | yfinance | `^IXIC`, `^DJI`, `^GSPC` |
| Nikkei / Hang Seng / FTSE / DAX | yfinance | `^N225`, `^HSI`, `^FTSE`, `^GDAXI` |
| USD/KRW | yfinance | `KRW=X` |
| Korean tickers | yfinance | `005930.KS` / `.KQ` |
| US tickers | yfinance | `AAPL` |
| Crypto | yfinance | `BTC-USD` (24/7) |
| FX / futures | yfinance | `EUR=X`, `GC=F` (24/7) |
| Disclosures + name map | OpenDart | `list.json`, `corpCode.xml` |

### Polling cadence
- Either market open: **60 s**
- Both closed (overnight / weekend): **600 s** (auto dial-down)
- Crypto / FX / futures: **always 60 s** (market hours ignored)

### Ring buffer (short-window attributes)
- In-memory, deque(maxlen=300) per ticker ≈ 5 hours of history
- Cleared on HA restart (intentional trade-off)

### Dependency
`yfinance>=0.2.40` only. HA installs it.

### Out of scope (by design)
- ❌ Automated trading
- ❌ Direct brokerage integration
- ❌ Chart cards (use apexcharts-card)
- ❌ Backtesting

</details>

---

## 🔄 Migration guide

| From → To | Action |
|---|---|
| ≤v0.1.31 → v0.1.32+ | Korean-slug entity_ids (`sensor.hangug_*`) → English slugs. Recommend delete + re-add. |
| v0.1.32–v0.1.33 → v0.1.34+ | `sensor.kr_finance_kit_*` → `sensor.fi_*`. Delete + re-add or rename entity_ids manually. |
| ≤v0.1.43 → v0.1.44+ | Five new options (target_currency_krw, P/L alert, market_close events, global indices, disclosure filter) — open and save Options once. |
| ≤v0.1.47 → v0.1.48+ | config_flow 500 error fix (frontend-compatible selectors). |
| ≤v0.1.51 → v0.1.52 | Short-window minutes was briefly a CSV option (now removed). |
| ≤v0.1.52 → v0.1.53+ | Option dropped; sensor always emits 1/5/15/30/60/90/120/180-min attributes. Blueprint's number input picks one of those. |

---

## Troubleshooting

- Prices Unavailable → restart HA and wait 1–2 min. If persistent, open [Issues](https://github.com/redchupa/kr_finance_kit/issues)
- New options don't appear → **full HA Restart** (Reload won't flush translations)
- `already_in_progress` error → update to v0.1.47+, restart HA
- `Config flow 500 error` → update to v0.1.48+
- Deeper guide: [docs/installation-en.md](docs/installation-en.md)

---

## ☕ Sponsor

If this integration helps you out, a coffee is appreciated. 🙏

<table>
  <tr>
    <td align="center">
      <b>Toss (Korea)</b><br/>
      <img src="https://raw.githubusercontent.com/redchupa/kr_finance_kit/main/images/toss-donation.png" alt="Toss donation QR" width="200"/>
    </td>
    <td align="center">
      <b>PayPal</b><br/>
      <img src="https://raw.githubusercontent.com/redchupa/kr_finance_kit/main/images/paypal-donation.png" alt="PayPal donation QR" width="200"/>
    </td>
  </tr>
</table>

---

<sub>Bug reports and feature requests: [Issues](https://github.com/redchupa/kr_finance_kit/issues) | Changelog: [Releases](https://github.com/redchupa/kr_finance_kit/releases) | [MIT License](LICENSE)</sub>
