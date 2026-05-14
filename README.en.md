# KR Finance Kit

English · **[한국어](README.md)**

> **Korean and US equities, right in your Home Assistant dashboard.**
> Ask "What's Samsung Electronics trading at?" by voice.
> Get pushed when a holding drops.

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

## Who it's for

- Glance at KOSPI and your tickers on the wall panel before you leave for work — no phone needed
- Push a Telegram / mobile notification the instant a holding drops 5%
- Let anyone in the house ask "Hey Google, what's Samsung at?" by voice
- Get a one-line market summary right after market close, including P/L
- Receive a phone alert when a new disclosure is filed (audit, executive change, earnings)

All of this is free — no brokerage credentials required.

---

## 5-minute install

### Prerequisites (skip if already set up)

- Home Assistant
- [HACS](https://hacs.xyz) (the HA integration/card marketplace)

### Step 1 · Add the repository to HACS

1. In HA's left menu, click **HACS**
2. Top-right ⋮ menu → **Custom repositories**
3. Enter:
   - **Repository URL**: `https://github.com/redchupa/kr_finance_kit`
   - **Type**: `Integration`
4. Click **Add**

### Step 2 · Download

1. Search **KR Finance Kit** on the HACS main screen
2. Click the card → **Download** (bottom right) → confirm
3. **Restart Home Assistant** (Settings → System → Restart)

### Step 3 · Add the integration

1. **Settings** → **Devices & services** → bottom-right **+ Add integration**
2. Search for **"KR Finance Kit"** → click
3. Fill in (everything is optional — leave blank to skip):

   | Field | What it does | Example |
   |---|---|---|
   | **OpenDart API key** | Enables disclosure alerts + automatic company names (price-only without it) | `14ab...` (see below) |
   | **Korean tickers** | Tickers to watch, comma-separated | `005930, 000660, 035420` |
   | **US tickers** | US symbols, comma-separated | `AAPL, MSFT, TSLA` |
   | **Crypto / FX / futures** | Yahoo ticker form, fetched 24/7 regardless of market hours | `BTC-USD, ETH-USD, EUR=X, GC=F` |
   | Include KOSPI / KOSDAQ indices | Adds Korean index sensors | ☑ |
   | Include NASDAQ / Dow / S&P 500 indices | Adds US index sensors | ☑ |
   | Include USD/KRW FX | Adds FX sensor | ☑ |

4. **Submit** → done.

The form embeds clickable lookup links, so you can find ticker codes without leaving the screen.

---

## Finding ticker codes

### Korean tickers (6-digit numbers)

Easiest path: search the company on Naver Finance — the 6-digit number at the end of the URL is your ticker.

| Company | Code |
|---|---|
| Samsung Electronics | `005930` |
| SK Hynix | `000660` |
| NAVER | `035420` |
| Kakao | `035720.KQ` _← KOSDAQ tickers need a `.KQ` suffix_ |
| LG Energy Solution | `373220` |
| Hyundai Motor | `005380` |
| Kia | `000270` |

Lookup sites: [KRX listed companies](https://kind.krx.co.kr/corpgeneral/corpList.do?method=loadInitPage) · [Naver Finance](https://finance.naver.com/sise/sise_market_sum.naver) · [Daum Finance](https://finance.daum.net)

### US tickers (alphabetic symbols)

| Company | Symbol |
|---|---|
| Apple | `AAPL` |
| Microsoft | `MSFT` |
| Tesla | `TSLA` |
| NVIDIA | `NVDA` |
| Alphabet (Google) | `GOOGL` |
| Amazon | `AMZN` |

Lookup sites: [Yahoo Finance Lookup](https://finance.yahoo.com/lookup) · [Google Finance](https://www.google.com/finance)

---

## Getting an OpenDart key (optional, free, ~1 min)

OpenDart is Korea's FSS free disclosure API. Adding a key unlocks two things:

- **Automatic company names** — `sensor.kr_finance_kit_kr_005930` shows up as "Samsung Electronics"
- **New disclosure alerts** — a `binary_sensor` turns ON when a new filing is detected for a watched ticker

**How to get one**:
1. [Sign up at opendart.fss.or.kr](https://opendart.fss.or.kr/uss/umt/EgovMberInsertView.do)
2. After login, [apply for an API key](https://opendart.fss.or.kr/mng/apiUseStusUser.do)
3. Copy the key issued instantly and paste it into the integration form

**Price and FX sensors work fully without a key.** You can add one later, no rush.

---

## What you get

With Korean tickers `005930, 000660`, US `AAPL`, and an OpenDart key, you'll see:

```
Market indicators ────────────────────────────────
  KOSPI                         2,500.12  (+0.50%)
  KOSDAQ                          850.00  (-0.30%)
  USD/KRW                       1,400.00  (+0.10%)

Korean tickers ───────────────────────────────────
  Samsung Electronics           70,000 KRW  (+1.5%)
  SK Hynix                     130,000 KRW  (-2.0%)

US tickers ───────────────────────────────────────
  AAPL                          $200.00     (+3.0%)

Holdings (when quantity / cost basis is set) ─────
  KR holdings value                      700,000 KRW
  US holdings value                          $1,000
  Total value (KRW-converted)          2,100,000 KRW
  Total unrealized P/L (KRW)            +240,000 KRW

Disclosure alerts ────────────────────────────────
  Samsung Electronics — new filing  ← auto-ON
```

Each item is an HA sensor, so you can drop them into dashboard cards, automations, or voice queries.

---

## Your first automation

A minimal example — **notify when a ticker drops 5% or more**:

```yaml
alias: "Samsung drop alert"
trigger:
  - platform: numeric_state
    entity_id: sensor.kr_finance_kit_kr_005930   # ← replace with your ticker
    attribute: change_pct
    below: -5
action:
  - service: notify.mobile_app           # ← your notify service
    data:
      title: "Drop alert"
      message: "{{ trigger.to_state.name }} {{ state_attr(trigger.entity_id, 'change_pct') }}% down"
```

More examples (end-of-day digest, disclosure pings, etc.) live in [docs/examples/](docs/examples/).

---

## Blueprints for ticker-based alerts

**Register many tickers in the integration, then check which ones you want alerts for — no rebuilding automations when you change your mind.** Adjusting the ticker list is a checkbox edit in the blueprint inputs.

Two blueprints are provided:

### 1. Price-change alert

Pushes when any selected ticker crosses a +/- threshold (e.g. +5% / -5%).

[![Open your Home Assistant instance and import this blueprint.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fredchupa%2Fkr_finance_kit%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fkr_finance_kit%2Fprice_change_alert.yaml)

Manual import URL: `https://github.com/redchupa/kr_finance_kit/blob/main/blueprints/automation/kr_finance_kit/price_change_alert.yaml`

Inputs: tickers to watch (multi-select) · drop threshold (e.g. `-5`) · rise threshold (e.g. `5`) · **notify target** (notify entities like `mobile_app_*`, pick from a searchable dropdown).

### 2. Daily market summary

At a configurable time (defaults to Korean market close, 15:30 KST), sends one message with KOSPI/KOSDAQ, FX, selected tickers, and holdings value/P&L.

[![Open your Home Assistant instance and import this blueprint.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fredchupa%2Fkr_finance_kit%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fkr_finance_kit%2Fdaily_summary.yaml)

Manual import URL: `https://github.com/redchupa/kr_finance_kit/blob/main/blueprints/automation/kr_finance_kit/daily_summary.yaml`

### How to import (same for both)

1. Click the **Import blueprint** badge above → HA opens the import dialog.
2. Or: **Settings → Automations & Scenes → Blueprints → Import Blueprint**, paste the URL.
3. Then **Create Automation → Use this blueprint** → fill in tickers/thresholds/notify service → save.

To add or remove a ticker later, edit the automation's blueprint inputs — no need to recreate the automation.

> **Notify compatibility note**: Both blueprints use the `notify.send_message` service (the HA 2024.6+ standard). **mobile_app** (HA Companion) auto-registers as a notify entity and shows up in the dropdown. If a service-only notify integration (e.g. some telegram_bot modes) doesn't appear, fall back to the raw YAML examples under [docs/examples/](docs/examples/) for that integration.

---

## Ask by voice

The integration registers automatically with HA Voice Assist, so you can ask:

| You say | You get |
|---|---|
| "What's KOSPI at?" | "KOSPI 2,500.12, up 0.5%" |
| "Samsung Electronics quote" | "Samsung Electronics 70,000 KRW, up 1.5%" |
| "What's the exchange rate?" | "USD/KRW 1,400 won" |
| "Today's biggest gainer?" | The top mover among your holdings/watchlist |
| "Summarize the market" | Indices + FX + total value in one breath |
| "Any new disclosures for my watchlist?" | Filings in the last 24 hours |

Works with `Google Assistant`, `Alexa`, `ChatGPT voice mode`, and `local Whisper` — anything that speaks to HA Assist.

---

## FAQ

<details>
<summary><b>Does it connect to my brokerage account?</b></summary>

**No.** Unofficial brokerage APIs carry security and legal risk and are intentionally left out. Quotes come from yfinance (Yahoo Finance's public chart API), disclosures from OpenDart (FSS official). For holdings P/L, you enter quantity and cost basis yourself.
</details>

<details>
<summary><b>Is it paid? Do the API keys cost money?</b></summary>

**Everything is free.** yfinance and OpenDart are both free with personal-use limits that you won't hit. The integration itself is MIT-licensed open source.
</details>

<details>
<summary><b>Will I get rate-limited or blocked since it scrapes?</b></summary>

**It doesn't scrape.** No Naver Finance HTML parsing — yfinance hits Yahoo Finance's official chart API, OpenDart uses the government's official API. Polling auto-drops from 60s to 600s when both KR and US markets are closed, so traffic is minimal.
</details>

<details>
<summary><b>Does it still work after market close or on weekends?</b></summary>

**Yes.** The last available close is shown. Korean and US holidays are both auto-detected.
</details>

<details>
<summary><b>How do I enter my holdings for P/L?</b></summary>

After setup, call the **`kr_finance_kit.add_position`** service from **Developer tools → Services**, passing ticker / quantity / cost basis / market (KR or US). Automations can call it too. The values stay in HA's encrypted store and never leave your instance.
</details>

<details>
<summary><b>Can I get charts too?</b></summary>

This integration ships sensors only. Plug them into [apexcharts-card](https://github.com/RomRider/apexcharts-card) (separate HACS) or HA's built-in statistics card. Example YAML lives in the examples folder.
</details>

<details>
<summary><b>My voice assistant doesn't see the integration's tool.</b></summary>

Open Settings → Voice Assistants → click your assistant → check that KR Finance Kit's tool is **exposed**. Also make sure you're using an LLM-backed assistant (e.g. OpenAI Conversation) — the basic pattern-matching one can't handle free-form quote queries.
</details>

<details>
<summary><b>How do I change options later?</b></summary>

**Settings → Devices & services → KR Finance Kit → ⚙ gear → Options.**
Existing values are pre-filled — adjust tickers or the OpenDart key and save.
</details>

---

<details>
<summary>Technical details (for developers / power users)</summary>

### Data sources

| Data | Source | API |
|---|---|---|
| KOSPI / KOSDAQ | yfinance | `^KS11`, `^KQ11` |
| NASDAQ / Dow / S&P 500 | yfinance | `^IXIC`, `^DJI`, `^GSPC` |
| USD/KRW | yfinance | `KRW=X` |
| Korean tickers | yfinance | `005930.KS` / `.KQ` |
| US tickers | yfinance | `AAPL` |
| Crypto / FX / futures | yfinance | `BTC-USD`, `EUR=X`, `GC=F` etc (24/7) |
| Disclosures + company-name mapping | OpenDart | `list.json`, `corpCode.xml` |

### Entities created

- `sensor.kr_finance_kit_kospi` / `_kosdaq` — Korean indices
- `sensor.kr_finance_kit_nasdaq` / `_dow` / `_sp500` — US indices (`^IXIC` / `^DJI` / `^GSPC`)
- `sensor.kr_finance_kit_usdkrw` — FX
- `sensor.kr_finance_kit_kr_<code>` — Korean ticker (attrs: `price`, `change`, `change_pct`, `asof`, `stale`)
- `sensor.kr_finance_kit_us_<symbol>` — US ticker
- `sensor.kr_finance_kit_other_<slug>` — crypto / FX / futures (e.g. `_btc_usd`, `_eth_usd`, `_eur_x`, `_gc_f`). 24/7 fetch.
- `sensor.kr_finance_kit_portfolio_*` — six P/L sensors (KR/US/KRW-converted × value/pl)
- `binary_sensor.kr_finance_kit_disclosure_<corp_code>` — 24h disclosure trigger

### LLM tool

A single `finance_query` function with 8 query types:
- `index` / `fx` / `quote` / `portfolio` / `disclosures` / `disclosure_for_ticker` / `top_movers` / `market_summary`

### Polling policy

- Either KR or US market open: 60s
- Both closed (overnight / weekend): 600s (auto dial-down)
- Korean holidays: yfinance's previous close + `stale=true` flag

### Security posture

- The OpenDart key lives only in HA's encrypted ConfigEntry store (masked in UI)
- Holdings quantity / cost basis stay in ConfigEntry options — never leave your instance
- Two NaN/inf guard layers (data + sensor) shield HA from corrupt yfinance rows
- All examples and test fixtures use synthetic data

### Dependencies

`yfinance>=0.2.40` — that's it. HA installs it for you.

### Out of scope (by design)

- Automated trading (legal / TOS risk)
- Direct brokerage account integration
- Chart cards (use apexcharts-card)
- Backtesting

</details>

---

## Migration to v0.1.32 (Korean → English entity_id)

Before v0.1.32, the integration's device friendly-names were in Korean ("한국 시장 지표" etc.), so HA generated Korean-slug entity_ids like `sensor.hangug_sijang_jipyo_kospi`. v0.1.32 adds `_attr_suggested_object_id` to every sensor, forcing newly-registered entities to use the documented English slugs (`sensor.kr_finance_kit_kospi`, etc.). HA's entity registry keeps existing IDs as-is, so already-installed entries don't auto-rename.

To switch to the English IDs (one-time):

1. **Easy**: Settings → Devices & services → KR Finance Kit → ⋮ → **Delete** → re-add. Re-enter holdings (quantity / cost basis) via the `kr_finance_kit.add_position` service afterward.
2. **Manual**: Settings → Devices & services → Entities → click each entity → gear icon → edit entity ID. Update any automations that referenced the old IDs.

After that, re-import the blueprints (or re-edit existing ones) and the ticker dropdown will show the clean English entity_ids.

---

## Troubleshooting

- Prices show as Unavailable → restart HA and wait 1–2 minutes. If it persists, file an [Issue](https://github.com/redchupa/kr_finance_kit/issues) with logs.
- Options dialog shows old text → HA Settings → System → **Restart** (not Reload)
- Company names show as codes → OpenDart key is empty. Get one and put it in Options.
- Deeper guide: [docs/installation-en.md](docs/installation-en.md)

---

## Sponsor

If this integration helps you out, a coffee is appreciated.

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
