/*
 * Finance Kit — sidebar panel (v0.2.0)
 *
 * Build-free single Web Component. Talks to the integration only through
 * the `kr_finance_kit/*` websocket commands registered in panel.py and the
 * existing add_position / remove_position services.
 *
 * Rendering model: three persistent regions (header, scroller content,
 * sheet overlay). Periodic data refreshes only re-render the content, so an
 * open sheet (with inputs the user is typing into) is never clobbered.
 */

const PANEL_VERSION = "0.2.10";
const LS_KEY = "kr_finance_kit.prefs";

const I18N = {
  ko: {
    title: "Finance Kit",
    loading: "데이터를 불러오는 중…",
    warming: "첫 시세를 가져오는 중입니다. 잠시만 기다려 주세요.",
    not_configured: "Finance Kit 통합이 아직 설정되지 않았습니다. 설정 → 기기 및 서비스에서 추가해 주세요.",
    refresh: "새로고침",
    settings: "설정",
    add: "종목 추가",
    updated: "업데이트",
    ago_s: "{n}초 전", ago_m: "{n}분 전", ago_h: "{n}시간 전",
    tab_all: "전체", tab_market: "시장", tab_watch: "관심", tab_portfolio: "보유", tab_news: "공시",
    sec_summary: "오늘의 시장", sec_indices: "지수", sec_watchlist: "관심 종목", sec_crypto: "코인",
    sec_portfolio: "내 보유 종목", sec_disclosures: "최근 공시",
    kr_market: "한국장", us_market: "미국장",
    open: "장중", closed: "장 마감",
    until_close: "마감까지 {t}", until_open: "개장까지 {t}",
    usdkrw: "원/달러",
    kimchi: "김치 프리미엄",
    kimchi_hint: "국내 거래소 원화 가격 ÷ (해외 달러 가격 × 환율)",
    total_value: "총 평가금액", total_pl: "평가손익", kr_sub: "국내", us_sub: "해외",
    no_positions: "아직 등록한 보유 종목이 없어요. 종목을 눌러 상세 화면에서 수량과 평단가를 입력하세요.",
    no_watch: "관심 종목이 없어요. ➕ 버튼으로 주식이나 코인을 추가해 보세요.",
    no_crypto: "코인이 없어요. ➕ → 코인 에서 BTC, ETH 등을 추가해 보세요.",
    no_disclosures: "최근 공시가 없습니다.",
    disclosure_off: "OpenDart API 키를 설정하면 보유·관심 종목의 공시가 여기에 표시됩니다.",
    no_indices: "표시할 지수가 없습니다. 통합 옵션에서 지수를 켜 주세요.",
    allocation: "보유 비중",
    qty: "수량", avg: "평단가", current: "현재가", value: "평가금액", pl: "손익",
    edit_order: "순서 편집", done: "완료",
    // add sheet
    add_title: "종목 추가",
    m_kr: "🇰🇷 국내", m_us: "🇺🇸 미국", m_crypto: "🪙 코인", m_other: "🌐 기타",
    search_ph: "이름 또는 코드 검색 (예: 삼성전자, AAPL, 비트코인)",
    ticker: "코드", label: "표시 이름 (선택)",
    ticker_ph_kr: "005930", ticker_ph_us: "AAPL", ticker_ph_crypto: "BTC", ticker_ph_other: "EUR=X, GC=F",
    quote_ccy: "기준 통화",
    quick: "빠른 선택",
    lookup_sites: "종목코드 검색 사이트",
    browse_title: "종목 선택해서 바로 추가",
    catalog_loading: "종목 데이터를 불러오는 중…",
    catalog_empty: "표시할 종목이 없어요.",
    already_added: "추가됨",
    quick_add: "추가",
    direct_input: "직접 코드 입력",
    adding: "추가하는 중…",
    added: "{t} 추가됨 — 시세가 곧 표시됩니다",
    removed: "{t} 삭제됨",
    searching: "검색 중…",
    no_results: "검색 결과가 없어요. 코드를 직접 입력해도 됩니다.",
    add_hint_kr: "6자리 종목코드. 코스닥은 뒤에 .KQ (예: 035720.KQ)",
    add_hint_us: "미국 티커 심볼 (예: AAPL, MSFT, BRK-B)",
    add_hint_crypto: "코인 심볼 + 기준 통화. 원화(KRW)와 달러(USD)를 둘 다 추가하면 김치 프리미엄이 계산돼요.",
    add_hint_other: "야후 파이낸스 심볼 (환율 EUR=X, 금 GC=F, 유가 CL=F)",
    err_invalid_ticker: "코드 형식이 올바르지 않아요.",
    err_invalid_kr_ticker: "국내 종목은 6자리 숫자 코드예요 (예: 005930).",
    err_invalid_us_ticker: "미국 종목은 영문 티커예요 (예: AAPL).",
    err_duplicate: "이미 관심 목록에 있어요.",
    err_no_quote: "시세를 찾지 못했어요. 코드를 확인하거나 '그래도 추가'를 눌러 주세요.",
    err_has_position: "보유 수량이 등록된 종목이에요. 삭제하면 보유 기록도 함께 지워집니다.",
    err_unauthorized: "관리자만 변경할 수 있어요.",
    err_generic: "요청을 처리하지 못했어요: {m}",
    force_add: "그래도 추가",
    force_remove: "보유 기록까지 삭제",
    // detail
    prev_close: "전일 종가", day_range: "일중 범위", w52: "52주 범위", volume: "거래량",
    per: "PER", div_yield: "배당수익률", krw_price: "원화 환산",
    my_position: "내 보유",
    price_alert: "🔔 가격 알림 (선택)",
    alert_high: "목표가 (이상)",
    alert_low: "손절가 (이하)",
    alert_hit_high: "목표가 도달",
    alert_hit_low: "손절가 도달",
    alert_hint: "도달 시 HA 가격 알림 센서(binary_sensor)가 ON 되고 kr_finance_kit_price_alert 이벤트가 발생합니다.",
    err_alert_bounds: "손절가는 목표가보다 낮아야 해요.",
    err_qty_avg: "수량과 평단가는 0보다 큰 숫자를 입력해 주세요.",
    save: "저장", saving: "저장 중…", saved: "✓ 저장 완료", delete: "삭제", deleting: "삭제 중…", cancel: "취소", close: "닫기",
    position_saved: "저장 완료! 보유 정보가 반영되었습니다.",
    position_deleted: "삭제 완료! 보유 목록에서 제거되었습니다.",
    position_unsupported: "보유 입력은 국내·미국 주식만 지원합니다.",
    unit_krw: "원 (KRW)", unit_usd: "달러 (USD)",
    open_history: "HA 기록 보기",
    remove_watch: "관심 해제",
    confirm_tap: "한 번 더 누르면 삭제",
    chart_empty: "차트 데이터를 불러오지 못했어요.",
    chart_loading: "차트 불러오는 중…",
    stale: "전일 데이터",
    // settings
    s_language: "언어", lang_auto: "자동 (HA 설정)",
    s_theme: "카드 테마", s_layout: "카드 레이아웃",
    s_upcolor: "상승 색상", up_auto: "언어에 맞춤", up_red: "🔴 빨강 상승 (한국식)", up_green: "🟢 초록 상승 (글로벌)",
    s_sections: "섹션 순서 · 표시",
    s_display: "표시 옵션",
    sparkline: "미니 차트 표시", spark_period: "미니 차트 기간",
    compact_numbers: "큰 숫자 축약 (1.2억, 3.4M)",
    show_krw: "달러 자산 원화 환산 표시",
    refresh_every: "자동 새로고침",
    sec_unit: "{n}초", min_unit: "{n}분",
    reset: "기본값으로 초기화",
    reset_done: "설정을 초기화했어요",
    about: "정보",
    about_text: "무료 공개 데이터(Yahoo Finance, OpenDart) 기반이며 지연될 수 있습니다. 투자 판단의 참고용으로만 사용하세요.",
    layout_cards: "카드", layout_list: "리스트", layout_compact: "컴팩트",
    layout_big: "빅넘버", layout_heatmap: "히트맵", layout_tape: "티커테이프",
    p_1d: "1일", p_5d: "5일", p_1mo: "1개월", p_6mo: "6개월", p_1y: "1년",
    kind_stock: "주식", kind_crypto: "코인", kind_fx: "환율", kind_future: "선물", kind_index: "지수", kind_other: "기타",
    readonly: "보기 전용 (관리자만 종목을 추가·삭제할 수 있어요)",
  },
  en: {
    title: "Finance Kit",
    loading: "Loading…",
    warming: "Fetching the first quotes. This takes a few seconds.",
    not_configured: "Finance Kit isn't set up yet. Add it under Settings → Devices & services.",
    refresh: "Refresh",
    settings: "Settings",
    add: "Add symbol",
    updated: "Updated",
    ago_s: "{n}s ago", ago_m: "{n}m ago", ago_h: "{n}h ago",
    tab_all: "All", tab_market: "Markets", tab_watch: "Watch", tab_portfolio: "Holdings", tab_news: "Filings",
    sec_summary: "Market today", sec_indices: "Indices", sec_watchlist: "Watchlist", sec_crypto: "Crypto",
    sec_portfolio: "My holdings", sec_disclosures: "Recent filings",
    kr_market: "Korea", us_market: "US",
    open: "Open", closed: "Closed",
    until_close: "closes in {t}", until_open: "opens in {t}",
    usdkrw: "USD/KRW",
    kimchi: "Kimchi premium",
    kimchi_hint: "Korean exchange KRW price ÷ (global USD price × FX)",
    total_value: "Total value", total_pl: "Unrealized P/L", kr_sub: "Korea", us_sub: "US",
    no_positions: "No holdings yet. Tap a symbol and enter quantity + average price in its detail view.",
    no_watch: "Your watchlist is empty. Use ➕ to add stocks or crypto.",
    no_crypto: "No crypto yet. Use ➕ → Crypto to add BTC, ETH and more.",
    no_disclosures: "No recent filings.",
    disclosure_off: "Set an OpenDart API key to see Korean corporate filings here.",
    no_indices: "No indices enabled. Turn them on in the integration options.",
    allocation: "Allocation",
    qty: "Qty", avg: "Avg price", current: "Price", value: "Value", pl: "P/L",
    edit_order: "Reorder", done: "Done",
    add_title: "Add symbol",
    m_kr: "🇰🇷 Korea", m_us: "🇺🇸 US", m_crypto: "🪙 Crypto", m_other: "🌐 Other",
    search_ph: "Search by name or code (e.g. Samsung, AAPL, Bitcoin)",
    ticker: "Symbol", label: "Display name (optional)",
    ticker_ph_kr: "005930", ticker_ph_us: "AAPL", ticker_ph_crypto: "BTC", ticker_ph_other: "EUR=X, GC=F",
    quote_ccy: "Quote currency",
    quick: "Quick pick",
    lookup_sites: "Find ticker codes",
    browse_title: "Pick & add from list",
    catalog_loading: "Loading symbols…",
    catalog_empty: "No symbols to show.",
    already_added: "Added",
    quick_add: "Add",
    direct_input: "Enter code manually",
    adding: "Adding…",
    added: "{t} added — quotes will appear shortly",
    removed: "{t} removed",
    searching: "Searching…",
    no_results: "No matches. You can still type the code directly.",
    add_hint_kr: "6-digit KRX code. KOSDAQ needs .KQ (e.g. 035720.KQ)",
    add_hint_us: "US ticker symbol (e.g. AAPL, MSFT, BRK-B)",
    add_hint_crypto: "Coin symbol + quote currency. Add both KRW and USD pairs to get the kimchi premium.",
    add_hint_other: "Yahoo Finance symbol (FX EUR=X, gold GC=F, oil CL=F)",
    err_invalid_ticker: "That symbol format isn't valid.",
    err_invalid_kr_ticker: "Korean stocks use a 6-digit code (e.g. 005930).",
    err_invalid_us_ticker: "US stocks use a letter ticker (e.g. AAPL).",
    err_duplicate: "Already on your watchlist.",
    err_no_quote: "No price found. Check the symbol or press 'Add anyway'.",
    err_has_position: "This symbol has a recorded holding. Removing it also deletes the holding.",
    err_unauthorized: "Only administrators can change the watchlist.",
    err_generic: "Request failed: {m}",
    force_add: "Add anyway",
    force_remove: "Remove with holding",
    prev_close: "Prev close", day_range: "Day range", w52: "52-week range", volume: "Volume",
    per: "P/E", div_yield: "Div. yield", krw_price: "In KRW",
    my_position: "My position",
    price_alert: "🔔 Price alert (optional)",
    alert_high: "Target (≥)",
    alert_low: "Stop-loss (≤)",
    alert_hit_high: "Target hit",
    alert_hit_low: "Stop-loss hit",
    alert_hint: "Turns the HA price alert binary_sensor ON and fires kr_finance_kit_price_alert when reached.",
    err_alert_bounds: "Stop-loss must be lower than target price.",
    err_qty_avg: "Quantity and average price must be greater than 0.",
    save: "Save", saving: "Saving…", saved: "✓ Saved", delete: "Delete", deleting: "Deleting…", cancel: "Cancel", close: "Close",
    position_saved: "Saved! Your holding has been updated.",
    position_deleted: "Deleted! Removed from holdings.",
    position_unsupported: "Holdings are supported for Korean and US stocks only.",
    unit_krw: "KRW", unit_usd: "USD",
    open_history: "Open HA history",
    remove_watch: "Remove",
    confirm_tap: "Tap again to remove",
    chart_empty: "Couldn't load chart data.",
    chart_loading: "Loading chart…",
    stale: "prior session",
    s_language: "Language", lang_auto: "Auto (HA setting)",
    s_theme: "Card theme", s_layout: "Card layout",
    s_upcolor: "Gain color", up_auto: "Match language", up_red: "🔴 Red = up (Korean)", up_green: "🟢 Green = up (Global)",
    s_sections: "Sections — order & visibility",
    s_display: "Display",
    sparkline: "Show mini charts", spark_period: "Mini chart range",
    compact_numbers: "Abbreviate big numbers (1.2M)",
    show_krw: "Show KRW value for USD assets",
    refresh_every: "Auto refresh",
    sec_unit: "{n}s", min_unit: "{n} min",
    reset: "Reset to defaults",
    reset_done: "Settings reset",
    about: "About",
    about_text: "Built on free public data (Yahoo Finance, OpenDart) which may be delayed. For reference only — not investment advice.",
    layout_cards: "Cards", layout_list: "List", layout_compact: "Compact",
    layout_big: "Big number", layout_heatmap: "Heatmap", layout_tape: "Ticker tape",
    p_1d: "1D", p_5d: "5D", p_1mo: "1M", p_6mo: "6M", p_1y: "1Y",
    kind_stock: "Stock", kind_crypto: "Crypto", kind_fx: "FX", kind_future: "Futures", kind_index: "Index", kind_other: "Other",
    readonly: "View only (only administrators can add or remove symbols)",
  },
};

const THEMES = [
  { id: "ha", ko: "HA 기본", en: "HA default", sw: ["#03a9f4", "#ffffff", "#212121"] },
  { id: "midnight", ko: "미드나잇", en: "Midnight", sw: ["#0b1220", "#131c2e", "#4f8cff"] },
  { id: "paper", ko: "페이퍼", en: "Paper", sw: ["#f6f1e7", "#fffdf8", "#b5651d"] },
  { id: "terminal", ko: "터미널", en: "Terminal", sw: ["#050805", "#0a120a", "#39ff14"] },
  { id: "neon", ko: "네온", en: "Neon", sw: ["#0d0221", "#1a0b3d", "#ff2bd6"] },
  { id: "glass", ko: "글래스", en: "Glass", sw: ["#667eea", "#764ba2", "#ffffff"] },
  { id: "ocean", ko: "오션", en: "Ocean", sw: ["#e8f4f8", "#ffffff", "#0096c7"] },
  { id: "sunset", ko: "선셋", en: "Sunset", sw: ["#ffe3ec", "#fffaf6", "#ff6b35"] },
  { id: "forest", ko: "포레스트", en: "Forest", sw: ["#0f1a14", "#16251c", "#4caf7a"] },
  { id: "mono", ko: "모노", en: "Mono", sw: ["#ffffff", "#f2f2f2", "#111111"] },
  { id: "pastel", ko: "파스텔", en: "Pastel", sw: ["#f7f5ff", "#ffffff", "#9b8cff"] },
  { id: "ink", ko: "먹 (한지)", en: "Ink", sw: ["#f3efe6", "#fbf8f1", "#b3261e"] },
  { id: "amoled", ko: "AMOLED 블랙", en: "AMOLED black", sw: ["#000000", "#0a0a0a", "#00d1ff"] },
];
const LAYOUTS = [
  { id: "cards", icon: "▦" },
  { id: "list", icon: "☰" },
  { id: "compact", icon: "▪▪" },
  { id: "big", icon: "▉" },
  { id: "heatmap", icon: "▩" },
  { id: "tape", icon: "⇆" },
];
const SECTION_IDS = ["summary", "indices", "watchlist", "crypto", "portfolio", "disclosures"];
const VIEWS = {
  all: SECTION_IDS,
  market: ["summary", "indices"],
  watch: ["watchlist", "crypto"],
  portfolio: ["portfolio"],
  news: ["disclosures"],
};
const VIEW_ICONS = { all: "◎", market: "📈", watch: "⭐", portfolio: "💼", news: "📰" };
const PERIODS = ["1d", "5d", "1mo", "6mo", "1y"];
const REFRESH_CHOICES = [15, 30, 60, 120, 300];
const FALLBACK_LOOKUP_URLS = {
  KR: [
    { label_ko: "KRX 상장법인 목록", label_en: "KRX Listed Companies", url: "https://kind.krx.co.kr/corpgeneral/corpList.do?method=loadInitPage" },
    { label_ko: "네이버 금융 시세", label_en: "Naver Finance", url: "https://finance.naver.com/sise/sise_market_sum.naver" },
  ],
  US: [
    { label_ko: "Yahoo Finance 종목 검색", label_en: "Yahoo Finance Lookup", url: "https://finance.yahoo.com/lookup" },
  ],
  CRYPTO: [
    { label_ko: "Yahoo Finance 코인 목록", label_en: "Yahoo Finance Crypto", url: "https://finance.yahoo.com/markets/crypto/all/" },
    { label_ko: "Yahoo Finance 검색", label_en: "Yahoo Finance Lookup", url: "https://finance.yahoo.com/lookup" },
  ],
  OTHER: [
    { label_ko: "Yahoo Finance 검색", label_en: "Yahoo Finance Lookup", url: "https://finance.yahoo.com/lookup" },
    { label_ko: "Yahoo Finance 원자재·선물", label_en: "Yahoo Finance Commodities", url: "https://finance.yahoo.com/markets/commodities/" },
  ],
};
const DEFAULT_PREFS = {
  lang: "auto", theme: "ha", layout: "cards", up_color: "auto",
  sections: SECTION_IDS.map((id) => ({ id, visible: true })),
  sparkline: true, spark_period: "1mo", refresh_sec: 30,
  compact_numbers: false, show_krw: true, order: [],
};
const INDEX_NAMES = {
  ko: { KOSPI: "코스피", KOSDAQ: "코스닥", NASDAQ: "나스닥", DOW: "다우존스", SP500: "S&P 500", NIKKEI: "니케이 225", HANGSENG: "항셍", FTSE: "FTSE 100", DAX: "DAX" },
  en: { KOSPI: "KOSPI", KOSDAQ: "KOSDAQ", NASDAQ: "Nasdaq", DOW: "Dow Jones", SP500: "S&P 500", NIKKEI: "Nikkei 225", HANGSENG: "Hang Seng", FTSE: "FTSE 100", DAX: "DAX" },
};
const GROUP_FLAG = { KR: "🇰🇷", US: "🇺🇸", GLOBAL: "🌐", OTHER: "🌐" };
const CCY_SYMBOL = { KRW: "₩", USD: "$", EUR: "€", JPY: "¥", GBP: "£", CNY: "¥", HKD: "HK$" };

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function hashHue(str) {
  let h = 0;
  for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) % 360;
  return h;
}

// Client-side mirror of panel_data.sanitize_prefs. Local copies come from
// localStorage, which can hold anything (old versions, manual edits); an
// unchecked refresh_sec of "abc" would make setInterval spin at 0 ms and a
// non-array `sections` would crash rendering.
function sanitizePrefs(raw) {
  const src = raw && typeof raw === "object" ? raw : {};
  const out = JSON.parse(JSON.stringify(DEFAULT_PREFS));
  const pick = (key, allowed) => { if (allowed.includes(src[key])) out[key] = src[key]; };
  pick("lang", ["auto", "ko", "en"]);
  pick("theme", THEMES.map((t) => t.id));
  pick("layout", LAYOUTS.map((l) => l.id));
  pick("up_color", ["auto", "red", "green"]);
  pick("spark_period", PERIODS);
  for (const key of ["sparkline", "compact_numbers", "show_krw"]) {
    if (typeof src[key] === "boolean") out[key] = src[key];
  }
  if (typeof src.refresh_sec === "number" && isFinite(src.refresh_sec)) {
    out.refresh_sec = Math.min(600, Math.max(10, Math.floor(src.refresh_sec)));
  }
  if (Array.isArray(src.sections)) {
    const seen = new Set();
    const secs = [];
    for (const s of src.sections) {
      if (s && SECTION_IDS.includes(s.id) && !seen.has(s.id)) {
        seen.add(s.id);
        secs.push({ id: s.id, visible: s.visible !== false });
      }
    }
    for (const id of SECTION_IDS) if (!seen.has(id)) secs.push({ id, visible: true });
    out.sections = secs;
  }
  if (Array.isArray(src.order)) {
    out.order = [...new Set(src.order.filter((k) => typeof k === "string" && /^(KR|US|OTHER):[A-Z0-9^][A-Z0-9.\-=^]{0,23}$/.test(k)))].slice(0, 200);
  }
  return out;
}

class KRFinancePanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._prefs = JSON.parse(JSON.stringify(DEFAULT_PREFS));
    this._snap = null;
    this._view = "all";
    this._sheet = null; // {type:'settings'|'add'|'detail', ...}
    this._edit = false;
    this._spark = {}; // period -> key -> {t,c}
    this._sparkPending = new Set();
    this._sparkFailed = new Set();
    this._catalogCache = {}; // "lang:market:category" -> catalog payload
    this._timers = [];
    this._built = false;
  }

  // ---------------------------------------------------------------- HA props
  set hass(h) {
    const first = !this._hass;
    this._hass = h;
    if (first) this._init();
  }
  get hass() { return this._hass; }
  set narrow(v) {
    this._narrow = !!v;
    if (this._built) { this._applyTheme(); this._renderHeader(); this._renderTabs(); }
  }
  get narrow() { return this._narrow; }
  set panel(p) { this._panelCfg = p; }
  set route(_r) {}

  connectedCallback() {
    if (this._hass && this._built && !this._timers.length) this._startTimers();
  }
  disconnectedCallback() { this._stopTimers(); }

  // ---------------------------------------------------------------- i18n
  get lang() {
    if (this._prefs.lang === "ko" || this._prefs.lang === "en") return this._prefs.lang;
    const hl = (this._hass && (this._hass.locale?.language || this._hass.language)) || navigator.language || "en";
    return String(hl).toLowerCase().startsWith("ko") ? "ko" : "en";
  }
  get locale() { return this.lang === "ko" ? "ko-KR" : "en-US"; }
  t(key, vars) {
    let s = (I18N[this.lang] && I18N[this.lang][key]) ?? I18N.en[key] ?? key;
    if (vars) for (const [k, v] of Object.entries(vars)) s = s.replace(`{${k}}`, v);
    return s;
  }
  get upColor() {
    if (this._prefs.up_color === "red" || this._prefs.up_color === "green") return this._prefs.up_color;
    return this.lang === "ko" ? "red" : "green";
  }
  get isAdmin() { return !!(this._snap?.is_admin ?? this._hass?.user?.is_admin); }

  // ---------------------------------------------------------------- lifecycle
  async _init() {
    this._buildShell();
    try {
      const ls = localStorage.getItem(LS_KEY);
      if (ls) this._prefs = sanitizePrefs(JSON.parse(ls));
    } catch (_e) { /* private mode or corrupt JSON */ }
    this._applyTheme();
    this._renderAll();
    try {
      const res = await this._hass.callWS({ type: "kr_finance_kit/prefs/get" });
      if (res && res.prefs && (res.stored || !localStorage.getItem(LS_KEY))) this._prefs = sanitizePrefs(res.prefs);
    } catch (_e) { /* backend older than panel — keep local prefs */ }
    this._applyTheme();
    this._renderAll();
    await this._loadSnapshot();
    this._startTimers();
  }

  _startTimers() {
    this._stopTimers();
    const every = Math.max(10, this._prefs.refresh_sec || 30) * 1000;
    this._timers.push(setInterval(() => { if (!document.hidden) this._loadSnapshot(); }, every));
    this._timers.push(setInterval(() => this._tick(), 1000));
    // Long-lived wall tablets: let mini charts refresh twice an hour.
    this._timers.push(setInterval(() => { this._spark = {}; this._sparkFailed.clear(); this._ensureSparks(); }, 30 * 60 * 1000));
    this._onVis = () => { if (!document.hidden) this._loadSnapshot(); };
    document.addEventListener("visibilitychange", this._onVis);
  }
  _stopTimers() {
    this._timers.forEach((id) => clearInterval(id));
    this._timers = [];
    if (this._onVis) document.removeEventListener("visibilitychange", this._onVis);
  }

  async _loadSnapshot() {
    if (!this._hass) return;
    try {
      const snap = await this._hass.callWS({ type: "kr_finance_kit/snapshot" });
      this._error = null;
      // Adding a symbol reloads the integration: for a few seconds the
      // backend reports "not configured" and then "no data yet". Keep the
      // last good snapshot on screen instead of flashing an empty page.
      const prev = this._snap;
      if (prev?.ready && (!snap.configured || !snap.ready) && (this._gap = (this._gap || 0) + 1) <= 8) {
        this._snap = { ...prev, is_admin: snap.is_admin ?? prev.is_admin };
      } else {
        this._gap = 0;
        this._snap = snap;
      }
    } catch (e) {
      this._error = e?.message || String(e);
    }
    this._renderHeader();
    this._renderContent();
    if (this._sheet?.type === "detail") this._refreshDetailLive();
    this._ensureSparks();
  }

  // ---------------------------------------------------------------- prefs
  _setPrefs(patch, { rerender = true } = {}) {
    this._prefs = { ...this._prefs, ...patch };
    try { localStorage.setItem(LS_KEY, JSON.stringify(this._prefs)); } catch (_e) { /* ignore */ }
    clearTimeout(this._saveTimer);
    this._saveTimer = setTimeout(() => {
      this._hass.callWS({ type: "kr_finance_kit/prefs/set", prefs: patch }).catch(() => {});
    }, 400);
    if ("refresh_sec" in patch) this._startTimers();
    if ("spark_period" in patch || "sparkline" in patch) this._ensureSparks();
    this._applyTheme();
    if (rerender) this._renderAll();
  }

  // ---------------------------------------------------------------- shell
  _buildShell() {
    this.shadowRoot.innerHTML = `<style>${STYLES}</style>
      <div class="root" id="root">
        <header id="header"></header>
        <nav class="tabs top" id="tabsTop"></nav>
        <div class="scroller" id="scroller"><main id="content"></main><div class="bottom-pad"></div></div>
        <nav class="tabs bottom" id="tabsBottom"></nav>
        <div id="sheet"></div>
        <div class="toast" id="toast" role="status" aria-live="polite"></div>
      </div>`;
    const root = this.shadowRoot.getElementById("root");
    root.addEventListener("click", (e) => this._onClick(e));
    root.addEventListener("change", (e) => this._onChange(e));
    root.addEventListener("input", (e) => this._onInput(e));
    root.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && this._sheet) this._closeSheet();
      if (e.key === "Enter" && e.target?.dataset?.enter) { e.preventDefault(); this._dispatch(e.target.dataset.enter, e.target); }
    });
    this._built = true;
  }

  _applyTheme() {
    const root = this.shadowRoot.getElementById("root");
    if (!root) return;
    root.className = `root t-${this._prefs.theme} up-${this.upColor} ${this._narrow ? "narrow" : ""}`;
    root.setAttribute("lang", this.lang);
  }

  _renderAll() {
    this._applyTheme();
    this._renderHeader();
    this._renderTabs();
    this._renderContent();
    this._renderSheet();
  }

  _headerSig() {
    return `${!!this._snap?.configured}:${this.isAdmin}:${this.lang}:${!!this._narrow}`;
  }

  _renderHeader() {
    const h = this.shadowRoot.getElementById("header");
    if (!h) return;
    this._hdrSig = this._headerSig();
    const menu = this._narrow
      ? `<button class="icon-btn" data-act="menu" aria-label="menu">☰</button>` : "";
    h.innerHTML = `
      ${menu}
      <div class="brand">
        <div class="title">${esc(this.t("title"))}</div>
        <div class="sub" data-ago>${esc(this._agoText())}</div>
      </div>
      <div class="actions">
        <button class="icon-btn" data-act="refresh" title="${esc(this.t("refresh"))}" aria-label="${esc(this.t("refresh"))}">⟳</button>
        <button class="pill-btn" data-act="lang" title="Language">${this.lang === "ko" ? "EN" : "한"}</button>
        <button class="icon-btn" data-act="settings" title="${esc(this.t("settings"))}" aria-label="${esc(this.t("settings"))}">⚙</button>
        ${this._snap?.configured && this.isAdmin
          ? `<button class="add-btn" data-act="add" title="${esc(this.t("add"))}" aria-label="${esc(this.t("add"))}"><span class="plus">＋</span><span class="add-l">${esc(this.t("add"))}</span></button>`
          : ""}
      </div>`;
  }

  _renderTabs() {
    const html = Object.keys(VIEWS).map((v) => `
      <button class="tab ${this._view === v ? "on" : ""}" data-act="view" data-view="${v}">
        <span class="ti">${VIEW_ICONS[v]}</span><span class="tl">${esc(this.t("tab_" + v))}</span>
      </button>`).join("");
    this.shadowRoot.getElementById("tabsTop").innerHTML = html;
    this.shadowRoot.getElementById("tabsBottom").innerHTML = html;
  }

  // ---------------------------------------------------------------- formatting
  _num(v, opts = {}) {
    if (v === null || v === undefined || !isFinite(v)) return "—";
    return new Intl.NumberFormat(this.locale, opts).format(v);
  }
  _decimals(v, ccy) {
    const a = Math.abs(v);
    if (ccy === "KRW") return a >= 100 ? 0 : 2;
    if (a >= 1) return 2;
    if (a >= 0.01) return 4;
    return 6;
  }
  _price(v, ccy, { symbol = true } = {}) {
    if (v === null || v === undefined || !isFinite(v)) return "—";
    const d = this._decimals(v, ccy);
    let s;
    if (this._prefs.compact_numbers && Math.abs(v) >= 1e6) {
      s = this._num(v, { notation: "compact", maximumFractionDigits: 2 });
    } else {
      s = this._num(v, { minimumFractionDigits: ccy === "KRW" ? 0 : Math.min(d, 2), maximumFractionDigits: d });
    }
    const sym = symbol && ccy ? CCY_SYMBOL[ccy] ?? "" : "";
    return sym ? `${v < 0 ? "-" : ""}${sym}${s.replace("-", "")}` : s;
  }
  _money(v, ccy) {
    if (v === null || v === undefined || !isFinite(v)) return "—";
    const sign = v > 0 ? "+" : "";
    return sign + this._price(v, ccy);
  }
  _pct(v) {
    if (v === null || v === undefined || !isFinite(v)) return "—";
    return `${v > 0 ? "+" : ""}${v.toFixed(2)}%`;
  }
  _dir(v) { return !isFinite(v) || v === null || v === 0 ? "flat" : v > 0 ? "up" : "down"; }
  _arrow(v) { const d = this._dir(v); return d === "up" ? "▲" : d === "down" ? "▼" : "–"; }
  _dur(ms) {
    if (ms < 0) ms = 0;
    const s = Math.floor(ms / 1000);
    const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
    if (d > 0) return this.lang === "ko" ? `${d}일 ${h}시간` : `${d}d ${h}h`;
    const pad = (n) => String(n).padStart(2, "0");
    return h > 0 ? `${h}:${pad(m)}:${pad(sec)}` : `${m}:${pad(sec)}`;
  }
  _agoText() {
    const iso = this._snap?.fetched_at;
    if (!iso) return this._error ? `⚠ ${this._error}` : "";
    const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
    const ago = s < 60 ? this.t("ago_s", { n: s }) : s < 3600 ? this.t("ago_m", { n: Math.floor(s / 60) }) : this.t("ago_h", { n: Math.floor(s / 3600) });
    return `${this.t("updated")} ${ago}`;
  }
  _tick() {
    const root = this.shadowRoot;
    root.querySelectorAll("[data-ago]").forEach((el) => { el.textContent = this._agoText(); });
    root.querySelectorAll("[data-countdown]").forEach((el) => {
      const target = new Date(el.dataset.countdown).getTime();
      const key = el.dataset.open === "1" ? "until_close" : "until_open";
      el.textContent = this.t(key, { t: this._dur(target - Date.now()) });
      if (target - Date.now() < -2000 && !this._sessionReload) {
        this._sessionReload = true;
        setTimeout(() => { this._sessionReload = false; this._loadSnapshot(); }, 1500);
      }
    });
  }

  // ---------------------------------------------------------------- data helpers
  _indexName(key) { return INDEX_NAMES[this.lang][key] || key; }
  _orderedQuotes(filterFn) {
    const quotes = (this._snap?.quotes || []).filter(filterFn);
    const order = this._prefs.order || [];
    const pos = (k) => { const i = order.indexOf(k); return i < 0 ? 1e6 : i; };
    return quotes
      .map((q, i) => ({ q, i }))
      .sort((a, b) => pos(a.q.key) - pos(b.q.key) || a.i - b.i)
      .map((x) => x.q);
  }
  _findItem(key) {
    if (!this._snap) return null;
    if (key.startsWith("INDEX:")) {
      const k = key.slice(6);
      const r = this._snap.indices.find((x) => x.key === k);
      return r ? { ...r, hkey: key, name: this._indexName(k), ticker: k, market: "INDEX", kind: "index", currency: null } : null;
    }
    if (key.startsWith("FX:")) {
      const k = key.slice(3);
      const r = this._snap.fx.find((x) => x.key === k);
      return r ? { ...r, hkey: key, name: this.t("usdkrw"), ticker: k, market: "FX", kind: "fx", currency: "KRW" } : null;
    }
    const r = this._snap.quotes.find((x) => x.key === key);
    return r ? { ...r, hkey: key } : null;
  }
  _sparkFor(key, period) { return (this._spark[period || this._prefs.spark_period] || {})[key]; }

  async _ensureSparks() {
    if (!this._prefs.sparkline || !this._snap?.ready) return;
    const period = this._prefs.spark_period;
    const keys = [
      ...(this._snap.indices || []).map((i) => "INDEX:" + i.key),
      ...(this._snap.quotes || []).map((q) => q.key),
    ];
    const missing = keys.filter((k) => !this._sparkFor(k, period) && !this._sparkPending.has(period + k) && !this._sparkFailed.has(period + k));
    if (!missing.length) return;
    missing.forEach((k) => this._sparkPending.add(period + k));
    for (let i = 0; i < missing.length; i += 6) {
      const chunk = missing.slice(i, i + 6);
      await this._fetchHistory(chunk, period);
      chunk.forEach((k) => this._sparkPending.delete(period + k));
      this._scheduleContentRender();
    }
  }
  async _fetchHistory(keys, period) {
    const symbols = keys.map((k) => {
      const [market, ...rest] = k.split(":");
      return { market, ticker: rest.join(":") };
    });
    try {
      const res = await this._hass.callWS({ type: "kr_finance_kit/history", symbols, period });
      this._spark[period] = this._spark[period] || {};
      for (const k of keys) {
        const s = res.series?.[k];
        if (s && s.c && s.c.length > 1) this._spark[period][k] = s;
        else this._sparkFailed.add(period + k);
      }
    } catch (_e) {
      keys.forEach((k) => this._sparkFailed.add(period + k));
    }
  }
  _scheduleContentRender() {
    if (this._rafPending) return;
    this._rafPending = true;
    requestAnimationFrame(() => { this._rafPending = false; this._renderContent(); });
  }

  // ---------------------------------------------------------------- SVG
  _sparkSvg(series, w = 120, h = 36, cls = "") {
    if (!series || !series.c || series.c.length < 2) return `<div class="spark-ph ${cls}"></div>`;
    const c = series.c;
    const min = Math.min(...c), max = Math.max(...c);
    const span = max - min || 1;
    const pts = c.map((v, i) => `${((i / (c.length - 1)) * w).toFixed(1)},${(h - 2 - ((v - min) / span) * (h - 4)).toFixed(1)}`);
    const dir = c[c.length - 1] >= c[0] ? "up" : "down";
    return `<svg class="spark ${dir} ${cls}" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true">
      <polyline points="${pts.join(" ")}" fill="none" stroke="currentColor" stroke-width="1.6" vector-effect="non-scaling-stroke" stroke-linejoin="round" stroke-linecap="round"/></svg>`;
  }

  _chartSvg(series, ccy) {
    if (!series) return `<div class="chart-msg">${esc(this.t("chart_loading"))}</div>`;
    if (!series.c || series.c.length < 2) return `<div class="chart-msg">${esc(this.t("chart_empty"))}</div>`;
    const W = 600, H = 220, P = 6;
    const c = series.c;
    const min = Math.min(...c), max = Math.max(...c);
    const span = max - min || 1;
    const x = (i) => P + (i / (c.length - 1)) * (W - 2 * P);
    const y = (v) => P + 14 + (1 - (v - min) / span) * (H - 2 * P - 28);
    const line = c.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
    const area = `M${x(0)},${H - P} L${line.split(" ").join(" L")} L${x(c.length - 1)},${H - P} Z`;
    const dir = c[c.length - 1] >= c[0] ? "up" : "down";
    const iMax = c.indexOf(max), iMin = c.indexOf(min);
    const fmtD = (t) => new Date(t * 1000).toLocaleDateString(this.locale, { month: "short", day: "numeric" });
    return `<div class="chart-wrap ${dir}">
      <svg class="chart" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" data-chart="1">
        <defs><linearGradient id="g" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stop-color="currentColor" stop-opacity=".28"/><stop offset="1" stop-color="currentColor" stop-opacity="0"/>
        </linearGradient></defs>
        <path d="${area}" fill="url(#g)"/>
        <polyline points="${line}" fill="none" stroke="currentColor" stroke-width="2" vector-effect="non-scaling-stroke" stroke-linejoin="round"/>
        <line class="xh" x1="0" x2="0" y1="0" y2="${H}" stroke-width="1" vector-effect="non-scaling-stroke" opacity="0"/>
        <circle class="xd" r="4" cx="0" cy="0" opacity="0"/>
      </svg>
      <div class="chart-lbl max" style="left:${(x(iMax) / W) * 100}%">${esc(this._price(max, ccy))}</div>
      <div class="chart-lbl min" style="left:${(x(iMin) / W) * 100}%">${esc(this._price(min, ccy))}</div>
      <div class="chart-tip" hidden></div>
      <div class="chart-axis"><span>${esc(fmtD(series.t[0]))}</span><span>${esc(fmtD(series.t[series.t.length - 1]))}</span></div>
    </div>`;
  }

  _bindChart(series, ccy, period) {
    const wrap = this.shadowRoot.querySelector("#sheet .chart-wrap");
    if (!wrap || !series?.c?.length) return;
    const svg = wrap.querySelector("svg");
    const tip = wrap.querySelector(".chart-tip");
    const xh = svg.querySelector(".xh"), xd = svg.querySelector(".xd");
    const c = series.c, W = 600, H = 220, P = 6;
    const min = Math.min(...c), max = Math.max(...c), span = max - min || 1;
    const intraday = period === "1d" || period === "5d";
    const move = (ev) => {
      const r = svg.getBoundingClientRect();
      const px = ((ev.clientX - r.left) / r.width) * W;
      const i = Math.max(0, Math.min(c.length - 1, Math.round(((px - P) / (W - 2 * P)) * (c.length - 1))));
      const cx = P + (i / (c.length - 1)) * (W - 2 * P);
      const cy = P + 14 + (1 - (c[i] - min) / span) * (H - 2 * P - 28);
      xh.setAttribute("x1", cx); xh.setAttribute("x2", cx); xh.setAttribute("opacity", ".5");
      xd.setAttribute("cx", cx); xd.setAttribute("cy", cy); xd.setAttribute("opacity", "1");
      const d = new Date(series.t[i] * 1000);
      const when = intraday
        ? d.toLocaleString(this.locale, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })
        : d.toLocaleDateString(this.locale, { year: "numeric", month: "short", day: "numeric" });
      const chg = ((c[i] / c[0] - 1) * 100);
      tip.hidden = false;
      tip.innerHTML = `<b>${esc(this._price(c[i], ccy))}</b> <span class="${this._dir(chg)}">${esc(this._pct(chg))}</span><br><small>${esc(when)}</small>`;
      const left = Math.min(Math.max((cx / W) * r.width, 60), r.width - 60);
      tip.style.left = `${left}px`;
    };
    const leave = () => { tip.hidden = true; xh.setAttribute("opacity", "0"); xd.setAttribute("opacity", "0"); };
    svg.addEventListener("pointermove", move);
    svg.addEventListener("pointerdown", move);
    svg.addEventListener("pointerleave", leave);
    svg.addEventListener("pointercancel", leave);
  }

  // ---------------------------------------------------------------- content
  _renderContent() {
    const el = this.shadowRoot.getElementById("content");
    if (!el) return;
    const s = this._snap;
    let html = "";
    if (!s) {
      html = `<div class="empty big">${this._error ? "⚠ " + esc(this._error) : esc(this.t("loading"))}</div>`;
    } else if (!s.configured) {
      html = `<div class="empty big">${esc(s.entry_exists ? this.t("loading") : this.t("not_configured"))}</div>`;
    } else {
      const visible = this._view === "all"
        ? this._prefs.sections.filter((x) => x.visible).map((x) => x.id)
        : VIEWS[this._view];
      if (!s.ready) html += `<div class="banner">⏳ ${esc(this.t("warming"))}</div>`;
      if (!this.isAdmin) html += `<div class="banner subtle">🔒 ${esc(this.t("readonly"))}</div>`;
      for (const id of visible) {
        const fn = this[`_sec_${id}`];
        if (fn) html += fn.call(this);
      }
    }
    el.innerHTML = html;
    el.className = `layout-${this._prefs.layout}`;
    // Admin status / configured state can change with a snapshot — keep the
    // header's add button in sync (only re-render when it actually changed).
    if (this._headerSig() !== this._hdrSig) this._renderHeader();
    this._tick();
  }

  _section(id, body, extra = "") {
    return `<section class="sec" data-sec="${id}">
      <div class="sec-h"><h2>${esc(this.t("sec_" + id))}</h2>${extra}</div>
      ${body}</section>`;
  }

  _sec_summary() {
    const s = this._snap;
    const sess = (m, label) => {
      const x = s.sessions?.[m];
      if (!x) return "";
      return `<div class="chip sess ${x.open ? "open" : ""}">
        <span class="dot"></span><b>${GROUP_FLAG[m]} ${esc(label)}</b>
        <span>${esc(x.open ? this.t("open") : this.t("closed"))}</span>
        <span class="muted" data-countdown="${esc(x.next)}" data-open="${x.open ? 1 : 0}"></span>
      </div>`;
    };
    const fx = (s.fx || [])[0];
    const fxChip = fx ? `<button class="chip" data-act="detail" data-key="FX:${esc(fx.key)}">
        <b>💱 ${esc(this.t("usdkrw"))}</b><span class="mono">${esc(this._price(fx.price, null))}</span>
        <span class="${this._dir(fx.change_pct)}">${esc(this._pct(fx.change_pct))}</span></button>` : "";
    const kimchi = (s.kimchi || []).map((k) => `<div class="chip" title="${esc(this.t("kimchi_hint"))}">
        <b>🌶 ${esc(k.asset)} ${esc(this.t("kimchi"))}</b>
        <span class="mono ${this._dir(k.premium_pct)}">${esc(this._pct(k.premium_pct))}</span></div>`).join("");
    const p = s.portfolio || {};
    const hero = p.krw_total != null ? `<div class="hero">
        <div class="hero-l">${esc(this.t("total_value"))}</div>
        <div class="hero-v mono">${esc(this._price(p.krw_total, "KRW"))}</div>
        <div class="hero-c ${this._dir(p.krw_pl)} mono">${this._arrow(p.krw_pl)} ${esc(this._money(p.krw_pl, "KRW"))} (${esc(this._pct(p.krw_pl_pct))})</div>
      </div>` : "";
    return this._section("summary", `${hero}<div class="chips">${sess("KR", this.t("kr_market"))}${sess("US", this.t("us_market"))}${fxChip}${kimchi}</div>`);
  }

  _sec_indices() {
    const idx = this._snap.indices || [];
    if (!idx.length) return this._section("indices", `<div class="empty">${esc(this.t("no_indices"))}</div>`);
    const cards = idx.map((r) => {
      const key = "INDEX:" + r.key;
      return `<button class="idx" data-act="detail" data-key="${esc(key)}">
        <div class="idx-top"><span>${GROUP_FLAG[r.group] || ""} ${esc(this._indexName(r.key))}</span></div>
        <div class="idx-v mono">${esc(this._price(r.price, null))}</div>
        <div class="idx-c ${this._dir(r.change_pct)} mono">${this._arrow(r.change_pct)} ${esc(this._pct(r.change_pct))}</div>
        ${this._prefs.sparkline ? this._sparkSvg(this._sparkFor(key), 120, 28, "idx-spark") : ""}
      </button>`;
    }).join("");
    return this._section("indices", `<div class="hscroll">${cards}</div>`);
  }

  _sec_watchlist() {
    const items = this._orderedQuotes((q) => q.kind !== "crypto");
    const editBtn = this.isAdmin && items.length > 1
      ? `<button class="link-btn" data-act="edit">${esc(this._edit ? this.t("done") : this.t("edit_order"))}</button>` : "";
    const body = items.length ? this._items(items) : `<div class="empty">${esc(this.t("no_watch"))}${this._addCta("KR")}</div>`;
    return this._section("watchlist", body, editBtn);
  }

  _sec_crypto() {
    const items = this._orderedQuotes((q) => q.kind === "crypto");
    const body = items.length ? this._items(items) : `<div class="empty">${esc(this.t("no_crypto"))}${this._addCta("CRYPTO")}</div>`;
    return this._section("crypto", body);
  }

  _addCta(market) {
    return this.isAdmin ? `<div><button class="btn primary sm" data-act="add" data-market="${market}">＋ ${esc(this.t("add"))}</button></div>` : "";
  }

  _items(items) {
    const layout = this._prefs.layout;
    if (layout === "tape") {
      const row = items.map((q) => `<button class="tape-item" data-act="detail" data-key="${esc(q.key)}">
          <b>${esc(q.name)}</b><span class="mono">${esc(this._price(q.price, q.currency))}</span>
          <span class="${this._dir(q.change_pct)} mono">${this._arrow(q.change_pct)}${esc(this._pct(q.change_pct))}</span></button>`).join("");
      const dup = items.length > 3 ? row : "";
      return `<div class="tape ${items.length > 3 ? "anim" : ""}"><div class="tape-track">${row}${dup}</div></div>
        ${this._edit ? `<div class="grid">${items.map((q, i) => this._item(q, i, items.length, "list")).join("")}</div>` : ""}`;
    }
    return `<div class="grid">${items.map((q, i) => this._item(q, i, items.length, layout)).join("")}</div>`;
  }

  _avatar(q) {
    const label = q.kind === "crypto" ? q.ticker.split("-")[0].slice(0, 4) : (q.name || q.ticker).slice(0, 1);
    return `<span class="av" style="--h:${hashHue(q.ticker)}">${esc(label)}</span>`;
  }

  _item(q, i, n, layout) {
    const dir = this._dir(q.change_pct);
    const spark = this._prefs.sparkline ? this._sparkFor(q.key) : null;
    const krw = this._prefs.show_krw && q.price_krw != null
      ? `<span class="krw mono">≈ ${esc(this._price(q.price_krw, "KRW"))}</span>` : "";
    const badge = `<span class="badge">${GROUP_FLAG[q.market] || ""} ${esc(q.ticker)}</span>`;
    const stale = q.stale ? `<span class="badge warn">${esc(this.t("stale"))}</span>` : "";
    const edit = this._edit && this.isAdmin ? `<div class="edit-row">
        <button class="icon-btn sm" data-act="move" data-key="${esc(q.key)}" data-dir="-1" ${i === 0 ? "disabled" : ""}>▲</button>
        <button class="icon-btn sm" data-act="move" data-key="${esc(q.key)}" data-dir="1" ${i === n - 1 ? "disabled" : ""}>▼</button>
        <button class="icon-btn sm danger" data-act="remove" data-key="${esc(q.key)}">✕</button></div>` : "";
    const attrs = `data-act="detail" data-key="${esc(q.key)}"`;
    const change = `<span class="chg ${dir} mono">${this._arrow(q.change_pct)} ${esc(this._pct(q.change_pct))}</span>`;
    const price = `<span class="px mono">${esc(this._price(q.price, q.currency))}</span>`;

    if (layout === "list") {
      return `<div class="item list d-${dir}"><button class="hit" ${attrs}>
          ${this._avatar(q)}
          <span class="nm"><b>${esc(q.name)}</b>${badge}${stale}</span>
          ${this._prefs.sparkline ? `<span class="sp">${this._sparkSvg(spark, 80, 28)}</span>` : ""}
          <span class="rt">${price}${change}</span>
        </button>${edit}</div>`;
    }
    if (layout === "compact") {
      return `<div class="item compact d-${dir}"><button class="hit" ${attrs}>
          <b class="nm1">${esc(q.name)}</b>${price}${change}</button>${edit}</div>`;
    }
    if (layout === "big") {
      return `<div class="item big d-${dir}"><button class="hit" ${attrs}>
          <div class="row">${this._avatar(q)}<span class="nm"><b>${esc(q.name)}</b>${badge}${stale}</span></div>
          <div class="bigpx mono">${esc(this._price(q.price, q.currency))}</div>
          <div class="row2">${change}<span class="mono muted">${esc(this._money(q.change, q.currency))}</span>${krw}</div>
          ${this._prefs.sparkline ? this._sparkSvg(spark, 300, 60, "wide") : ""}
        </button>${edit}</div>`;
    }
    if (layout === "heatmap") {
      const mag = Math.min(1, Math.abs(q.change_pct || 0) / 5);
      return `<div class="item heat d-${dir}" style="--mag:${(0.12 + mag * 0.78).toFixed(2)}"><button class="hit" ${attrs}>
          <b class="nm1">${esc(q.name)}</b>
          <span class="heat-pct mono">${esc(this._pct(q.change_pct))}</span>
          <span class="mono heat-px">${esc(this._price(q.price, q.currency))}</span>
        </button>${edit}</div>`;
    }
    // cards (default)
    return `<div class="item card d-${dir}"><button class="hit" ${attrs}>
        <div class="row">${this._avatar(q)}<span class="nm"><b>${esc(q.name)}</b>${badge}${stale}</span></div>
        <div class="row2">${price}${change}</div>
        ${krw ? `<div class="row3">${krw}</div>` : ""}
        ${this._prefs.sparkline ? this._sparkSvg(spark, 200, 40, "wide") : ""}
      </button>${edit}</div>`;
  }

  _sec_portfolio() {
    const p = this._snap.portfolio || {};
    const rows = p.positions || [];
    if (!rows.length) return this._section("portfolio", `<div class="empty">${esc(this.t("no_positions"))}</div>`);
    const nameOf = (r) => (this._snap.quotes.find((q) => q.market === r.market && q.ticker === r.ticker)?.name) || r.ticker;
    const ccy = (r) => (r.market === "KR" ? "KRW" : "USD");
    const head = `<div class="pf-head">
        <div><div class="muted">${esc(this.t("total_value"))}</div><div class="pf-v mono">${esc(this._price(p.krw_total, "KRW"))}</div></div>
        <div><div class="muted">${esc(this.t("total_pl"))}</div><div class="pf-v mono ${this._dir(p.krw_pl)}">${esc(this._money(p.krw_pl, "KRW"))} <small>${esc(this._pct(p.krw_pl_pct))}</small></div></div>
        ${p.kr_value != null ? `<div><div class="muted">🇰🇷 ${esc(this.t("kr_sub"))}</div><div class="mono">${esc(this._price(p.kr_value, "KRW"))} <small class="${this._dir(p.kr_pl)}">${esc(this._money(p.kr_pl, "KRW"))}</small></div></div>` : ""}
        ${p.us_value != null ? `<div><div class="muted">🇺🇸 ${esc(this.t("us_sub"))}</div><div class="mono">${esc(this._price(p.us_value, "USD"))} <small class="${this._dir(p.us_pl)}">${esc(this._money(p.us_pl, "USD"))}</small></div></div>` : ""}
      </div>`;
    const weighted = rows.filter((r) => r.weight_pct > 0).sort((a, b) => b.weight_pct - a.weight_pct);
    const bar = weighted.length ? `<div class="muted small">${esc(this.t("allocation"))}</div>
      <div class="alloc">${weighted.map((r) => `<span style="flex:${r.weight_pct};--h:${hashHue(r.ticker)}" title="${esc(nameOf(r))} ${r.weight_pct}%"></span>`).join("")}</div>
      <div class="alloc-legend">${weighted.map((r) => `<span><i style="--h:${hashHue(r.ticker)}"></i>${esc(nameOf(r))} ${r.weight_pct.toFixed(1)}%</span>`).join("")}</div>` : "";
    const alertBadge = (r) => {
      if (r.alert_state === "high") return `<span class="alert-badge hit up">🔔 ${esc(this.t("alert_hit_high"))}</span>`;
      if (r.alert_state === "low") return `<span class="alert-badge hit down">🔔 ${esc(this.t("alert_hit_low"))}</span>`;
      const parts = [];
      if (r.alert_high != null) parts.push(`↑${this._price(r.alert_high, ccy(r))}`);
      if (r.alert_low != null) parts.push(`↓${this._price(r.alert_low, ccy(r))}`);
      return parts.length ? `<span class="alert-badge">🔔 ${esc(parts.join(" · "))}</span>` : "";
    };
    const list = rows.map((r) => `<button class="pf-row ${r.alert_state ? "pf-hit" : ""}" data-act="detail" data-key="${esc(r.market + ":" + r.ticker)}">
        <span class="nm"><b>${esc(nameOf(r))}</b><span class="muted small mono">${esc(this._num(r.quantity, { maximumFractionDigits: 4 }))} × ${esc(this._price(r.avg_price, ccy(r)))}</span>${alertBadge(r)}</span>
        <span class="rt"><span class="mono">${esc(this._price(r.value, ccy(r)))}</span>
          <span class="mono small ${this._dir(r.pl)}">${esc(this._money(r.pl, ccy(r)))} (${esc(this._pct(r.pl_pct))})</span></span>
      </button>`).join("");
    return this._section("portfolio", `${head}${bar}<div class="pf-list">${list}</div>`);
  }

  _sec_disclosures() {
    const s = this._snap;
    if (!s.disclosure_enabled) return this._section("disclosures", `<div class="empty">${esc(this.t("disclosure_off"))}</div>`);
    const rows = s.disclosures || [];
    if (!rows.length) return this._section("disclosures", `<div class="empty">${esc(this.t("no_disclosures"))}</div>`);
    const fmt = (d) => (d && d.length === 8 ? `${d.slice(4, 6)}/${d.slice(6, 8)}` : esc(d || ""));
    return this._section("disclosures", `<div class="disc">${rows.map((r) => `
      <a class="disc-row" href="${esc(/^https:\/\//i.test(r.url || "") ? r.url : "#")}" target="_blank" rel="noopener noreferrer">
        <span class="disc-d mono">${fmt(r.rcept_dt)}</span>
        <span class="disc-t"><b>${esc(r.corp_name)}</b><span>${esc(r.report_nm)}</span></span>
        <span class="muted">↗</span>
      </a>`).join("")}</div>`);
  }

  // ---------------------------------------------------------------- sheets
  _openSheet(sheet) { this._sheet = sheet; this._renderSheet(); }
  _closeSheet() { this._sheet = null; this._renderSheet(); }

  _renderSheet() {
    const el = this.shadowRoot.getElementById("sheet");
    if (!el) return;
    if (!this._sheet) { el.innerHTML = ""; this._sheetSig = null; return; }
    const prevBody = el.querySelector(".sheet-b");
    const sig = `${this._sheet.type}:${this._sheet.key || ""}`;
    const same = !!prevBody && this._sheetSig === sig;
    const prevScroll = same ? prevBody.scrollTop : 0;
    this._sheetSig = sig;
    let body = "";
    let title = "";
    if (this._sheet.type === "settings") { title = this.t("settings"); body = this._settingsBody(); }
    if (this._sheet.type === "add") { title = this.t("add_title"); body = this._addBody(); }
    if (this._sheet.type === "detail") { const it = this._findItem(this._sheet.key); title = it?.name || ""; body = this._detailBody(it); }
    el.innerHTML = `<div class="backdrop" data-act="close"></div>
      <div class="sheet" role="dialog" aria-modal="true" aria-label="${esc(title)}">
        <div class="grab"></div>
        <div class="sheet-h"><h3>${esc(title)}</h3><button class="icon-btn" data-act="close" aria-label="${esc(this.t("close"))}">✕</button></div>
        <div class="sheet-b">${body}</div>
      </div>`;
    if (same) {
      el.querySelector(".backdrop").classList.add("noanim");
      el.querySelector(".sheet").classList.add("noanim");
      el.querySelector(".sheet-b").scrollTop = prevScroll;
    }
    if (this._sheet.type === "detail") this._afterDetailRender();
    if (this._sheet.type === "add" && !same) {
      const inp = el.querySelector("#q");
      if (inp && !this._narrow) inp.focus();
    }
  }

  // ---- settings
  _settingsBody() {
    const p = this._prefs;
    const seg = (key, options) => `<div class="seg">${options.map(([v, l]) =>
      `<button class="${p[key] === v ? "on" : ""}" data-act="pref" data-key="${key}" data-val="${esc(v)}">${esc(l)}</button>`).join("")}</div>`;
    const themes = THEMES.map((th) => `<button class="theme ${p.theme === th.id ? "on" : ""}" data-act="pref" data-key="theme" data-val="${th.id}">
        <span class="sw t-${th.id}-sw" style="background:linear-gradient(135deg,${th.sw[0]} 0 50%,${th.sw[1]} 50% 100%)"><i style="background:${th.sw[2]}"></i></span>
        <span>${esc(th[this.lang] || th.en)}</span></button>`).join("");
    const layouts = LAYOUTS.map((l) => `<button class="theme ${p.layout === l.id ? "on" : ""}" data-act="pref" data-key="layout" data-val="${l.id}">
        <span class="lay">${l.icon}</span><span>${esc(this.t("layout_" + l.id))}</span></button>`).join("");
    const sections = p.sections.map((s, i) => `<div class="sec-row">
        <label class="sw-row"><input type="checkbox" data-act="secvis" data-id="${s.id}" ${s.visible ? "checked" : ""}><span>${esc(this.t("sec_" + s.id))}</span></label>
        <span><button class="icon-btn sm" data-act="secmove" data-id="${s.id}" data-dir="-1" ${i === 0 ? "disabled" : ""}>▲</button>
        <button class="icon-btn sm" data-act="secmove" data-id="${s.id}" data-dir="1" ${i === p.sections.length - 1 ? "disabled" : ""}>▼</button></span>
      </div>`).join("");
    const toggle = (key) => `<label class="sw-row"><input type="checkbox" data-act="prefbool" data-key="${key}" ${p[key] ? "checked" : ""}><span>${esc(this.t(key))}</span></label>`;
    const refresh = `<select data-act="prefnum" data-key="refresh_sec">${REFRESH_CHOICES.map((n) =>
      `<option value="${n}" ${p.refresh_sec === n ? "selected" : ""}>${esc(n < 60 ? this.t("sec_unit", { n }) : this.t("min_unit", { n: n / 60 }))}</option>`).join("")}</select>`;
    return `
      <h4>${esc(this.t("s_language"))}</h4>
      ${seg("lang", [["auto", this.t("lang_auto")], ["ko", "한국어"], ["en", "English"]])}
      <h4>${esc(this.t("s_theme"))}</h4><div class="theme-grid">${themes}</div>
      <h4>${esc(this.t("s_layout"))}</h4><div class="theme-grid">${layouts}</div>
      <h4>${esc(this.t("s_upcolor"))}</h4>
      ${seg("up_color", [["auto", this.t("up_auto")], ["red", this.t("up_red")], ["green", this.t("up_green")]])}
      <h4>${esc(this.t("s_sections"))}</h4><div class="sec-list">${sections}</div>
      <h4>${esc(this.t("s_display"))}</h4>
      ${toggle("sparkline")}
      <div class="field"><span>${esc(this.t("spark_period"))}</span>${seg("spark_period", PERIODS.map((x) => [x, this.t("p_" + x)]))}</div>
      ${toggle("compact_numbers")}
      ${toggle("show_krw")}
      <div class="field inline"><span>${esc(this.t("refresh_every"))}</span>${refresh}</div>
      <div class="field"><button class="btn" data-act="reset">${esc(this.t("reset"))}</button></div>
      <h4>${esc(this.t("about"))}</h4>
      <p class="muted small">${esc(this.t("about_text"))}<br>Finance Kit v${esc(this._snap?.version || this._panelCfg?.config?.version || PANEL_VERSION)}</p>`;
  }

  // ---- add
  _watchNormKey(market, symbol, quote) {
    const s = String(symbol || "").trim().toUpperCase();
    if (market === "KR") return `KR:${s.replace(/\.KS$/i, "")}`;
    if (market === "CRYPTO") {
      const q = (quote || "KRW").toUpperCase();
      return `OTHER:${s.includes("-") ? s : `${s}-${q}`}`;
    }
    return `${market}:${s}`;
  }
  _isWatched(market, symbol, quote) {
    const key = this._watchNormKey(market, symbol, quote);
    if (this._sheet?.justAdded?.has(key)) return true;
    for (const q of this._snap?.quotes || []) {
      const qKey = q.market === "KR" ? `KR:${String(q.ticker).toUpperCase().replace(/\.KS$/i, "")}` : `${q.market}:${String(q.ticker).toUpperCase()}`;
      if (qKey === key) return true;
    }
    return false;
  }
  _lookupLinks(market, cat) {
    if (cat?.links?.length) return cat.links;
    const isKo = this.lang === "ko";
    return (FALLBACK_LOOKUP_URLS[market] || []).map((l) => ({
      label: isKo ? l.label_ko : l.label_en,
      url: l.url,
    }));
  }
  _addBody() {
    const st = this._sheet;
    const m = st.market || "KR";
    const cat = st.catalog;
    const segBtn = (v) => `<button class="${m === v ? "on" : ""}" data-act="addmarket" data-val="${v}">${esc(this.t("m_" + v.toLowerCase()))}</button>`;
    const links = this._lookupLinks(m, cat);
    const linksHtml = links.length ? `<div class="lookup-box">
      <div class="lookup-h">🔗 ${esc(this.t("lookup_sites"))}</div>
      <div class="lookup-links">${links.map((l) =>
        `<a class="lookup-link" href="${esc(l.url)}" target="_blank" rel="noopener noreferrer" title="${esc(l.url)}">${esc(l.label)} ↗</a>`).join("")}</div>
    </div>` : "";
    const cryptoQuote = m === "CRYPTO" ? `<div class="field"><span>${esc(this.t("quote_ccy"))}</span><div class="seg">${["KRW", "USD", "USDT"].map((c) =>
      `<button class="${(st.quote || "KRW") === c ? "on" : ""}" data-act="addquote" data-val="${c}">${c}</button>`).join("")}</div></div>` : "";
    return `
      <div class="seg wide">${["KR", "US", "CRYPTO", "OTHER"].map(segBtn).join("")}</div>
      <p class="muted small">${esc(this.t("add_hint_" + m.toLowerCase()))}</p>
      ${linksHtml}
      <div class="field"><input id="q" class="inp" type="search" autocomplete="off" placeholder="${esc(this.t("search_ph"))}" value="${esc(st.query || "")}" data-act="search"></div>
      <div id="results" class="results">${this._resultsHtml()}</div>
      ${cryptoQuote}
      <div class="field">
        <span>${esc(this.t("browse_title"))}</span>
        <div id="catalog">${this._catalogHtml()}</div>
      </div>
      <div class="direct-box">
        <div class="muted small">${esc(this.t("direct_input"))}</div>
        <div class="field two">
          <label><span>${esc(this.t("ticker"))}</span><input id="tk" class="inp mono" autocapitalize="characters" autocomplete="off" placeholder="${esc(this.t("ticker_ph_" + m.toLowerCase()))}" value="${esc(st.ticker || "")}" data-enter="doadd"></label>
          <label><span>${esc(this.t("label"))}</span><input id="lb" class="inp" autocomplete="off" value="${esc(st.label || "")}" data-enter="doadd"></label>
        </div>
        <div id="adderr" class="err" ${st.error ? "" : "hidden"}>${esc(st.error || "")}</div>
        <div class="btn-row">
          ${st.canForce ? `<button class="btn" data-act="doadd" data-force="1">${esc(this.t("force_add"))}</button>` : ""}
          <button class="btn primary" data-act="doadd" ${st.busy ? "disabled" : ""}>${esc(st.busy ? this.t("adding") : this.t("add"))}</button>
        </div>
      </div>`;
  }
  _catalogHtml() {
    const st = this._sheet || {};
    const m = st.market || "KR";
    const quote = st.quote || "KRW";
    if (st.catLoading && !st.catalog) return `<div class="muted small pad">${esc(this.t("catalog_loading"))}</div>`;
    const cat = st.catalog;
    if (!cat) return "";
    const curCat = st.category || "all";
    const tabs = (cat.categories || []).length > 1
      ? `<div class="cat-tabs">${cat.categories.map((c) =>
          `<button class="cat-tab ${curCat === c.id ? "on" : ""}" data-act="cat" data-val="${esc(c.id)}">${esc(c.label)}</button>`).join("")}</div>` : "";
    const items = cat.items || [];
    if (!items.length) return `${tabs}<div class="muted small pad">${esc(this.t("catalog_empty"))}</div>`;
    const rows = items.map((r, i) => {
      const dispSym = m === "CRYPTO" ? `${r.symbol}-${quote}` : r.symbol;
      const watched = this._isWatched(m, r.symbol, quote);
      const adding = st.addingKey === this._watchNormKey(m, r.symbol, quote);
      return `<div class="cat-row">
        <button class="cat-pick" data-act="catpick" data-i="${i}">
          <span class="badge">${esc(dispSym)}</span>
          <span class="res-n"><b>${esc(r.name)}</b></span>
          <span class="muted small">${esc(r.exchange || "")}</span>
        </button>
        ${watched
          ? `<span class="cat-added">✓ ${esc(this.t("already_added"))}</span>`
          : `<button class="cat-add-btn" data-act="catadd" data-i="${i}" ${adding ? "disabled" : ""}>${adding ? "…" : `＋ ${esc(this.t("quick_add"))}`}</button>`}
      </div>`;
    }).join("");
    return `${tabs}<div class="cat-list">${rows}</div>`;
  }
  _updateCatalog() {
    const el = this.shadowRoot.getElementById("catalog");
    if (el) el.innerHTML = this._catalogHtml();
  }
  async _loadCatalog() {
    const st = this._sheet;
    if (!st || st.type !== "add") return;
    const market = st.market || "KR";
    const category = st.category || "all";
    const lang = this.lang;
    const cacheKey = `${lang}:${market}:${category}`;
    if (this._catalogCache[cacheKey]) {
      st.catalog = this._catalogCache[cacheKey];
      st.catLoading = false;
      this._updateCatalog();
      return;
    }
    st.catLoading = true;
    this._updateCatalog();
    try {
      const res = await this._hass.callWS({
        type: "kr_finance_kit/catalog",
        market,
        category,
        lang,
        limit: 80,
      });
      this._catalogCache[cacheKey] = res;
      if (!this._sheet || this._sheet.type !== "add" || (this._sheet.market || "KR") !== market || (this._sheet.category || "all") !== category) return;
      this._sheet.catalog = res;
    } catch (_e) {
      if (!this._sheet || this._sheet.type !== "add") return;
      this._sheet.catalog = { market, categories: [], items: [], links: this._lookupLinks(market, null) };
    }
    if (this._sheet && this._sheet.type === "add") {
      this._sheet.catLoading = false;
      this._updateCatalog();
    }
  }
  _resultsHtml() {
    const st = this._sheet || {};
    if (st.searching) return `<div class="muted small pad">${esc(this.t("searching"))}</div>`;
    if (!st.results) return "";
    if (!st.results.length) return `<div class="muted small pad">${esc(this.t("no_results"))}</div>`;
    const quote = st.quote || "KRW";
    return st.results.map((r, i) => {
      const watched = this._isWatched(r.market, r.symbol, quote);
      const adding = st.addingKey === this._watchNormKey(r.market, r.symbol, quote);
      return `<div class="cat-row">
        <button class="cat-pick" data-act="pick" data-i="${i}">
          <span class="badge">${GROUP_FLAG[r.market === "CRYPTO" ? "OTHER" : r.market] || "🌐"} ${esc(r.market === "CRYPTO" ? "🪙" : "")}${esc(r.symbol)}</span>
          <span class="res-n">${esc(r.name)}</span>
          <span class="muted small">${esc(r.exchange || "")}</span>
        </button>
        ${watched
          ? `<span class="cat-added">✓ ${esc(this.t("already_added"))}</span>`
          : `<button class="cat-add-btn" data-act="resadd" data-i="${i}" ${adding ? "disabled" : ""}>${adding ? "…" : `＋ ${esc(this.t("quick_add"))}`}</button>`}
      </div>`;
    }).join("");
  }
  _updateResults() {
    const el = this.shadowRoot.getElementById("results");
    if (el) el.innerHTML = this._resultsHtml();
  }
  _readAddInputs() {
    const r = this.shadowRoot;
    if (!this._sheet) return;
    this._sheet.ticker = r.getElementById("tk")?.value || "";
    this._sheet.label = r.getElementById("lb")?.value || "";
    this._sheet.query = r.getElementById("q")?.value || "";
  }
  async _doSearch(q) {
    if (!this._sheet || this._sheet.type !== "add") return;
    if (!q || q.trim().length < 1) { this._sheet.results = null; this._updateResults(); return; }
    this._sheet.searching = true; this._updateResults();
    try {
      const res = await this._hass.callWS({ type: "kr_finance_kit/search", query: q.trim(), lang: this.lang });
      if (!this._sheet || this._sheet.type !== "add" || this._sheet.query !== q) return;
      this._sheet.results = res.results || [];
    } catch (_e) {
      this._sheet.results = [];
    }
    this._sheet.searching = false;
    this._updateResults();
  }
  async _quickAddSymbol(market, symbol, label) {
    const st = this._sheet;
    if (!st || st.type !== "add" || st.addingKey) return;
    const quote = market === "CRYPTO" ? (symbol.includes("-") ? symbol.split("-").pop() : (st.quote || "KRW")) : undefined;
    const normKey = this._watchNormKey(market, symbol, quote);
    st.addingKey = normKey;
    st.error = null;
    this._updateCatalog();
    this._updateResults();
    const msg = { type: "kr_finance_kit/watchlist/add", market, ticker: symbol, force: false };
    if (market === "CRYPTO") msg.quote = quote;
    if (label && label.trim()) msg.label = label.trim();
    try {
      const res = await this._hass.callWS(msg);
      if (!st.justAdded) st.justAdded = new Set();
      st.justAdded.add(normKey);
      this._toast(this.t("added", { t: label || res.ticker }));
      this._pollAfterChange(res.market + ":" + res.ticker);
    } catch (e) {
      if (e?.code === "duplicate") {
        if (!st.justAdded) st.justAdded = new Set();
        st.justAdded.add(normKey);
      }
      this._toast(this._errText(e));
    }
    if (this._sheet && this._sheet.type === "add") {
      this._sheet.addingKey = null;
      this._updateCatalog();
      this._updateResults();
    }
  }
  async _doAdd(force) {
    this._readAddInputs();
    const st = this._sheet;
    if (!st || st.busy) return;
    const ticker = (st.ticker || "").trim();
    if (!ticker) { st.error = this.t("err_invalid_ticker"); this._renderSheet(); return; }
    st.busy = true; st.error = null; st.canForce = false; this._renderSheet();
    const msg = { type: "kr_finance_kit/watchlist/add", market: st.market || "KR", ticker, force: !!force };
    if ((st.market || "KR") === "CRYPTO") msg.quote = st.quote || "KRW";
    if (st.label && st.label.trim()) msg.label = st.label.trim();
    try {
      const res = await this._hass.callWS(msg);
      this._closeSheet();
      this._toast(this.t("added", { t: res.ticker }));
      this._pollAfterChange(res.market + ":" + res.ticker);
    } catch (e) {
      st.busy = false;
      st.error = this._errText(e);
      st.canForce = e?.code === "no_quote";
      this._renderSheet();
    }
  }
  _errText(e) {
    const code = e?.code;
    const known = I18N.en["err_" + code];
    if (known) return this.t("err_" + code);
    return this.t("err_generic", { m: e?.message || code || "?" });
  }
  _pollAfterChange(key) {
    let n = 0;
    const tick = async () => {
      n += 1;
      await this._loadSnapshot();
      const found = key ? this._findItem(key) : null;
      if (n < 12 && (!found || found.price == null)) setTimeout(tick, 2500);
    };
    setTimeout(tick, 1500);
  }

  // ---- detail
  _detailBody(it) {
    if (!it) return `<div class="empty">—</div>`;
    const st = this._sheet;
    const period = st.period || this._prefs.spark_period;
    const info = it.info || {};
    const ccy = it.currency;
    const stat = (label, val) => (val ? `<div class="stat"><span class="muted">${esc(label)}</span><b class="mono">${val}</b></div>` : "");
    const range = (lo, hi, cur) => {
      if (lo == null || hi == null || cur == null || hi <= lo) return "";
      const pos = Math.max(0, Math.min(100, ((cur - lo) / (hi - lo)) * 100));
      return `<div class="range"><span class="mono small">${esc(this._price(lo, ccy))}</span>
        <span class="range-bar"><i style="left:${pos}%"></i></span><span class="mono small">${esc(this._price(hi, ccy))}</span></div>`;
    };
    const stats = [
      stat(this.t("prev_close"), it.prev_close != null ? esc(this._price(it.prev_close, ccy)) : ""),
      stat(this.t("krw_price"), it.price_krw != null ? esc(this._price(it.price_krw, "KRW")) : ""),
      stat(this.t("volume"), info.regularMarketVolume != null ? esc(this._num(info.regularMarketVolume, { notation: "compact" })) : ""),
      stat(this.t("per"), info.trailingPE != null ? esc(this._num(info.trailingPE, { maximumFractionDigits: 1 })) : ""),
      stat(this.t("div_yield"), info.dividendYield != null ? esc(this._num(info.dividendYield, { maximumFractionDigits: 2 })) + "%" : ""),
    ].join("");
    const dayRange = range(info.regularMarketDayLow, info.regularMarketDayHigh, it.price);
    const wkRange = range(info.fiftyTwoWeekLow, info.fiftyTwoWeekHigh, it.price);
    const series = (this._spark[period] || {})[it.hkey];
    const failed = this._sparkFailed.has(period + it.hkey);
    const pos = (this._snap.portfolio?.positions || []).find((p) => p.market === it.market && p.ticker === it.ticker);
    const canHold = it.market === "KR" || it.market === "US";
    const unit = it.market === "KR" ? this.t("unit_krw") : this.t("unit_usd");
    const posSummary = pos && pos.pl != null
      ? `<div class="pos-sum ${this._dir(pos.pl)}"><b class="mono">${esc(this._money(pos.pl, ccy))}</b> <span class="mono">(${esc(this._pct(pos.pl_pct))})</span> · <span class="mono">${esc(this._price(pos.value, ccy))}</span></div>` : "";
    // Holdings are written through the add/remove_position services; the
    // panel only offers the form to administrators (read-only for others,
    // matching the watchlist controls).
    const alertBanner = pos?.alert_state
      ? `<div class="alert-banner ${pos.alert_state === "high" ? "up" : "down"}">🔔 ${esc(pos.alert_state === "high" ? this.t("alert_hit_high") : this.t("alert_hit_low"))} (${esc(this._price(pos.alert_state === "high" ? pos.alert_high : pos.alert_low, ccy))})</div>` : "";
    const roAlerts = pos && (pos.alert_high != null || pos.alert_low != null)
      ? `<p class="muted small mono">🔔 ${pos.alert_high != null ? `↑${esc(this._price(pos.alert_high, ccy))}` : ""} ${pos.alert_low != null ? `↓${esc(this._price(pos.alert_low, ccy))}` : ""}</p>` : "";
    const readOnlyHolding = pos
      ? `<h4>${esc(this.t("my_position"))}</h4>${alertBanner}${posSummary}<p class="muted small mono">${esc(this._num(pos.quantity, { maximumFractionDigits: 4 }))} × ${esc(this._price(pos.avg_price, ccy))}</p>${roAlerts}` : "";
    const posStatus = st.posStatus
      ? `<div id="posstatus" class="pos-status ${st.posStatus.kind}" role="status" aria-live="polite">${st.posStatus.kind === "ok" ? "✓" : "⚠"} ${esc(st.posStatus.text)}</div>`
      : `<div id="posstatus" class="pos-status" hidden></div>`;
    const saveCls = st.posSaved ? "btn saved" : "btn primary";
    const saveLbl = st.posBusy === "save" ? this.t("saving") : st.posSaved ? this.t("saved") : this.t("save");
    const delLbl = st.posBusy === "del" ? this.t("deleting") : this.t("delete");
    const holding = ["INDEX", "FX"].includes(it.market) ? "" : !this.isAdmin ? readOnlyHolding : `<h4>${esc(this.t("my_position"))}</h4>
      ${canHold ? `${alertBanner}${posSummary}
        <div class="field two">
          <label><span>${esc(this.t("qty"))}</span><input id="pq" class="inp mono" type="number" inputmode="decimal" min="0" step="any" data-posinp="1" value="${pos ? esc(pos.quantity) : ""}"></label>
          <label><span>${esc(this.t("avg"))} · ${esc(unit)}</span><input id="pa" class="inp mono" type="number" inputmode="decimal" min="0" step="any" data-posinp="1" value="${pos ? esc(pos.avg_price) : ""}"></label>
        </div>
        <div class="alert-box">
          <div class="muted small">${esc(this.t("price_alert"))}</div>
          <div class="field two">
            <label><span>${esc(this.t("alert_high"))} · ${esc(unit)}</span><input id="pah" class="inp mono" type="number" inputmode="decimal" min="0" step="any" data-posinp="1" placeholder="—" value="${pos?.alert_high != null ? esc(pos.alert_high) : ""}"></label>
            <label><span>${esc(this.t("alert_low"))} · ${esc(unit)}</span><input id="pal" class="inp mono" type="number" inputmode="decimal" min="0" step="any" data-posinp="1" placeholder="—" value="${pos?.alert_low != null ? esc(pos.alert_low) : ""}"></label>
          </div>
          <div class="muted small">${esc(this.t("alert_hint"))}</div>
        </div>
        ${posStatus}
        <div class="btn-row">${pos ? `<button class="btn danger" data-act="posdel" ${st.posBusy ? "disabled" : ""}>${esc(delLbl)}</button>` : ""}
          <button class="${saveCls}" data-act="possave" ${st.posBusy ? "disabled" : ""}>${esc(saveLbl)}</button></div>`
        : `<p class="muted small">${esc(this.t("position_unsupported"))}</p>`}`;
    return `
      <div class="d-top">
        <div><span class="badge">${GROUP_FLAG[it.market] || GROUP_FLAG[it.group] || "🌐"} ${esc(it.ticker)}</span>
          <span class="badge">${esc(this.t("kind_" + (it.kind || "other")))}</span>
          ${it.stale ? `<span class="badge warn">${esc(this.t("stale"))}</span>` : ""}</div>
        <div class="d-px mono" id="dpx">${esc(this._price(it.price, ccy))}</div>
        <div class="d-chg mono ${this._dir(it.change_pct)}" id="dchg">${this._arrow(it.change_pct)} ${esc(this._money(it.change, ccy))} (${esc(this._pct(it.change_pct))})</div>
      </div>
      <div class="seg wide">${PERIODS.map((x) => `<button class="${period === x ? "on" : ""}" data-act="period" data-val="${x}">${esc(this.t("p_" + x))}</button>`).join("")}</div>
      ${failed ? `<div class="chart-msg">${esc(this.t("chart_empty"))}</div>` : this._chartSvg(series, ccy)}
      ${dayRange ? `<div class="muted small">${esc(this.t("day_range"))}</div>${dayRange}` : ""}
      ${wkRange ? `<div class="muted small">${esc(this.t("w52"))}</div>${wkRange}` : ""}
      <div class="stats">${stats}</div>
      ${holding}
      <div class="btn-row">
        ${it.entity_id ? `<button class="btn" data-act="moreinfo" data-eid="${esc(it.entity_id)}">📈 ${esc(this.t("open_history"))}</button>` : ""}
        ${this.isAdmin && !["INDEX", "FX"].includes(it.market) ? `<button class="btn danger" data-act="remove" data-key="${esc(it.hkey)}">${esc(this.t("remove_watch"))}</button>` : ""}
      </div>`;
  }
  _afterDetailRender() {
    const it = this._findItem(this._sheet.key);
    if (!it) return;
    const period = this._sheet.period || this._prefs.spark_period;
    const series = (this._spark[period] || {})[it.hkey];
    if (series) {
      this._bindChart(series, it.currency, period);
    } else if (!this._sparkFailed.has(period + it.hkey) && !this._sparkPending.has(period + it.hkey)) {
      this._sparkPending.add(period + it.hkey);
      this._fetchHistory([it.hkey], period).then(() => {
        this._sparkPending.delete(period + it.hkey);
        if (this._sheet?.type === "detail" && this._sheet.key === it.hkey) this._renderDetailKeepInputs();
      });
    }
  }
  _renderDetailKeepInputs() {
    const r = this.shadowRoot;
    const q = r.getElementById("pq")?.value, a = r.getElementById("pa")?.value;
    const ah = r.getElementById("pah")?.value, al = r.getElementById("pal")?.value;
    const scroll = r.querySelector(".sheet-b")?.scrollTop || 0;
    this._renderSheet();
    if (q !== undefined && r.getElementById("pq")) r.getElementById("pq").value = q;
    if (a !== undefined && r.getElementById("pa")) r.getElementById("pa").value = a;
    if (ah !== undefined && r.getElementById("pah")) r.getElementById("pah").value = ah;
    if (al !== undefined && r.getElementById("pal")) r.getElementById("pal").value = al;
    const sb = r.querySelector(".sheet-b");
    if (sb) sb.scrollTop = scroll;
  }
  _refreshDetailLive() {
    const it = this._findItem(this._sheet.key);
    const r = this.shadowRoot;
    if (!it) return;
    const px = r.getElementById("dpx"), chg = r.getElementById("dchg");
    if (px) px.textContent = this._price(it.price, it.currency);
    if (chg) {
      chg.className = `d-chg mono ${this._dir(it.change_pct)}`;
      chg.textContent = `${this._arrow(it.change_pct)} ${this._money(it.change, it.currency)} (${this._pct(it.change_pct)})`;
    }
  }
  _setPosStatus(kind, text) {
    if (!this._sheet || this._sheet.type !== "detail") return;
    this._sheet.posStatus = kind ? { kind, text } : null;
    const el = this.shadowRoot.getElementById("posstatus");
    if (!el) return;
    if (!kind) {
      el.hidden = true;
      el.textContent = "";
      el.className = "pos-status";
      return;
    }
    el.hidden = false;
    el.className = `pos-status ${kind}`;
    el.textContent = `${kind === "ok" ? "✓" : "⚠"} ${text}`;
  }
  async _savePosition() {
    const st = this._sheet;
    if (!st || st.type !== "detail" || st.posBusy) return;
    const it = this._findItem(st.key);
    const r = this.shadowRoot;
    const qty = parseFloat(r.getElementById("pq")?.value);
    const avg = parseFloat(r.getElementById("pa")?.value);
    if (!(qty > 0) || !(avg > 0)) {
      const msg = this.t("err_qty_avg");
      this._setPosStatus("err", msg);
      this._toast(`⚠ ${msg}`);
      return;
    }
    const rawH = (r.getElementById("pah")?.value || "").trim();
    const rawL = (r.getElementById("pal")?.value || "").trim();
    const alertHigh = rawH ? parseFloat(rawH) : null;
    const alertLow = rawL ? parseFloat(rawL) : null;
    if (alertHigh !== null && !(alertHigh > 0)) {
      const msg = this.t("err_generic", { m: `${this.t("alert_high")} > 0` });
      this._setPosStatus("err", msg);
      this._toast(`⚠ ${msg}`);
      return;
    }
    if (alertLow !== null && !(alertLow > 0)) {
      const msg = this.t("err_generic", { m: `${this.t("alert_low")} > 0` });
      this._setPosStatus("err", msg);
      this._toast(`⚠ ${msg}`);
      return;
    }
    if (alertHigh !== null && alertLow !== null && alertLow >= alertHigh) {
      const msg = this.t("err_alert_bounds");
      this._setPosStatus("err", msg);
      this._toast(`⚠ ${msg}`);
      return;
    }
    const payload = { ticker: it.ticker, market: it.market, quantity: qty, avg_price: avg };
    if (alertHigh !== null) payload.alert_high = alertHigh;
    if (alertLow !== null) payload.alert_low = alertLow;
    st.posBusy = "save";
    st.posSaved = false;
    st.posStatus = null;
    this._renderDetailKeepInputs();
    try {
      await this._hass.callService("kr_finance_kit", "add_position", payload);
      if (this._sheet === st) {
        st.posBusy = null;
        st.posSaved = true;
        st.posStatus = { kind: "ok", text: this.t("position_saved") };
        this._renderDetailKeepInputs();
        clearTimeout(this._savedBtnTimer);
        this._savedBtnTimer = setTimeout(() => {
          if (this._sheet === st && st.posSaved) {
            st.posSaved = false;
            this._renderDetailKeepInputs();
          }
        }, 2500);
      }
      this._toast(`✓ ${this.t("position_saved")}`);
      this._pollAfterChange(null);
    } catch (e) {
      const msg = this._errText(e);
      if (this._sheet === st) {
        st.posBusy = null;
        st.posSaved = false;
        st.posStatus = { kind: "err", text: msg };
        this._renderDetailKeepInputs();
      }
      this._toast(`⚠ ${msg}`);
    }
  }
  async _deletePosition() {
    const st = this._sheet;
    if (!st || st.type !== "detail" || st.posBusy) return;
    const it = this._findItem(st.key);
    st.posBusy = "del";
    st.posSaved = false;
    st.posStatus = null;
    this._renderDetailKeepInputs();
    try {
      await this._hass.callService("kr_finance_kit", "remove_position", { ticker: it.ticker, market: it.market });
      if (this._sheet === st) {
        st.posBusy = null;
        st.posStatus = { kind: "ok", text: this.t("position_deleted") };
        // Clear inputs locally so the user immediately sees it's gone
        this._renderSheet();
        const r = this.shadowRoot;
        for (const id of ["pq", "pa", "pah", "pal"]) {
          const inp = r.getElementById(id);
          if (inp) inp.value = "";
        }
      }
      this._toast(`✓ ${this.t("position_deleted")}`);
      this._pollAfterChange(null);
    } catch (e) {
      const msg = this._errText(e);
      if (this._sheet === st) {
        st.posBusy = null;
        st.posStatus = { kind: "err", text: msg };
        this._renderDetailKeepInputs();
      }
      this._toast(`⚠ ${msg}`);
    }
  }
  // Two-tap confirmation instead of window.confirm(): the HA mobile apps'
  // WebViews don't reliably show native JS dialogs.
  _arm(btn, armKey, label) {
    if (this._armed === armKey) return true;
    this._armed = armKey;
    if (!btn.dataset.label) btn.dataset.label = btn.textContent;
    btn.textContent = label;
    btn.classList.add("armed");
    clearTimeout(this._armTimer);
    this._armTimer = setTimeout(() => {
      this._armed = null;
      btn.textContent = btn.dataset.label;
      btn.classList.remove("armed");
    }, 3500);
    return false;
  }
  async _removeWatch(key, btn) {
    const it = this._findItem(key);
    if (!it || !btn) return;
    const force = this._armed === `force:${key}`;
    if (!force && !this._arm(btn, `rm:${key}`, this.t("confirm_tap"))) return;
    this._armed = null;
    clearTimeout(this._armTimer);
    try {
      await this._hass.callWS({ type: "kr_finance_kit/watchlist/remove", market: it.market, ticker: it.ticker, force });
      if (this._sheet?.type === "detail") this._closeSheet();
      this._toast(this.t("removed", { t: it.name }));
      const order = (this._prefs.order || []).filter((k) => k !== key);
      if (order.length !== (this._prefs.order || []).length) this._setPrefs({ order }, { rerender: false });
      this._pollAfterChange(null);
    } catch (e) {
      if (e?.code === "has_position") {
        this._toast(this.t("err_has_position"));
        this._arm(btn, `force:${key}`, this.t("force_remove"));
        return;
      }
      btn.textContent = btn.dataset.label || btn.textContent;
      btn.classList.remove("armed");
      this._toast(this._errText(e));
    }
  }

  _toast(text) {
    const el = this.shadowRoot.getElementById("toast");
    if (!el) return;
    el.textContent = text;
    el.classList.add("show");
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => el.classList.remove("show"), 3200);
  }

  // ---------------------------------------------------------------- events
  _onClick(e) {
    const btn = e.target.closest("[data-act]");
    if (!btn || btn.disabled) return;
    const act = btn.dataset.act;
    if (["search", "secvis", "prefbool", "prefnum"].includes(act)) return; // handled by input/change
    if (btn.tagName === "A") return;
    e.preventDefault();
    this._dispatch(act, btn);
  }

  _dispatch(act, btn) {
    const d = btn.dataset;
    switch (act) {
      case "menu":
        this.dispatchEvent(new Event("hass-toggle-menu", { bubbles: true, composed: true }));
        break;
      case "refresh":
        this._toast("⟳");
        this._sparkFailed.clear();
        this._hass.callService("kr_finance_kit", "refresh_now", {}).catch(() => {}).finally(() => this._loadSnapshot());
        break;
      case "lang":
        this._setPrefs({ lang: this.lang === "ko" ? "en" : "ko" });
        break;
      case "settings": this._openSheet({ type: "settings" }); break;
      case "close": this._closeSheet(); break;
      case "view":
        this._view = d.view;
        this._renderTabs(); this._renderContent();
        this.shadowRoot.getElementById("scroller").scrollTop = 0;
        break;
      case "edit": this._edit = !this._edit; this._renderContent(); break;
      case "add":
        this._openSheet({ type: "add", market: d.market || "KR", category: "all", quote: this.lang === "ko" ? "KRW" : "USD", justAdded: new Set() });
        this._loadCatalog();
        break;
      case "detail": if (!this._edit) this._openSheet({ type: "detail", key: d.key }); break;
      case "pref": this._setPrefs({ [d.key]: d.val }); break;
      case "secmove": {
        const secs = [...this._prefs.sections];
        const i = secs.findIndex((s) => s.id === d.id), j = i + Number(d.dir);
        if (i < 0 || j < 0 || j >= secs.length) break;
        [secs[i], secs[j]] = [secs[j], secs[i]];
        this._setPrefs({ sections: secs });
        break;
      }
      case "move": {
        const all = this._orderedQuotes(() => true).map((q) => q.key);
        const i = all.indexOf(d.key);
        const item = this._findItem(d.key);
        const same = all.filter((k) => (this._findItem(k)?.kind === "crypto") === (item?.kind === "crypto"));
        const si = same.indexOf(d.key), sj = si + Number(d.dir);
        if (i < 0 || sj < 0 || sj >= same.length) break;
        const a = all.indexOf(same[si]), b = all.indexOf(same[sj]);
        [all[a], all[b]] = [all[b], all[a]];
        this._setPrefs({ order: all });
        break;
      }
      case "remove": this._removeWatch(d.key, btn); break;
      case "reset":
        this._setPrefs(JSON.parse(JSON.stringify(DEFAULT_PREFS)));
        this._toast(this.t("reset_done"));
        break;
      case "addmarket":
        this._readAddInputs();
        this._sheet.market = d.val;
        this._sheet.category = "all";
        this._sheet.catalog = null;
        this._sheet.error = null;
        this._sheet.canForce = false;
        this._renderSheet();
        this._loadCatalog();
        break;
      case "addquote":
        this._readAddInputs();
        this._sheet.quote = d.val;
        this._renderSheet();
        break;
      case "cat":
        this._readAddInputs();
        this._sheet.category = d.val;
        this._sheet.catalog = null;
        this._loadCatalog();
        break;
      case "catpick": {
        this._readAddInputs();
        const r = this._sheet.catalog?.items?.[Number(d.i)];
        if (!r) break;
        this._sheet.ticker = r.symbol;
        this._sheet.label = r.name || "";
        this._sheet.error = null;
        this._renderSheet();
        break;
      }
      case "catadd": {
        const r = this._sheet.catalog?.items?.[Number(d.i)];
        if (r) this._quickAddSymbol(this._sheet.market || r.market || "KR", r.symbol, r.name || "");
        break;
      }
      case "resadd": {
        const r = this._sheet.results?.[Number(d.i)];
        if (r) this._quickAddSymbol(r.market, r.symbol, r.name || "");
        break;
      }
      case "pick": {
        this._readAddInputs();
        const r = this._sheet.results?.[Number(d.i)];
        if (!r) break;
        this._sheet.market = r.market;
        if (r.market === "CRYPTO" && r.symbol.includes("-")) this._sheet.quote = r.symbol.split("-").pop();
        this._sheet.ticker = r.symbol;
        this._sheet.label = r.name || "";
        this._sheet.error = null;
        this._renderSheet();
        this._loadCatalog();
        break;
      }
      case "doadd": this._doAdd(d.force === "1"); break;
      case "period":
        this._sheet.period = d.val;
        this._renderDetailKeepInputs();
        break;
      case "possave": this._savePosition(); break;
      case "posdel": this._deletePosition(); break;
      case "moreinfo":
        this.dispatchEvent(new CustomEvent("hass-more-info", { detail: { entityId: d.eid }, bubbles: true, composed: true }));
        break;
      default: break;
    }
  }

  _onChange(e) {
    const el = e.target;
    const act = el.dataset?.act;
    if (act === "secvis") {
      const secs = this._prefs.sections.map((s) => (s.id === el.dataset.id ? { ...s, visible: el.checked } : s));
      this._setPrefs({ sections: secs });
    } else if (act === "prefbool") {
      this._setPrefs({ [el.dataset.key]: el.checked });
    } else if (act === "prefnum") {
      this._setPrefs({ [el.dataset.key]: Number(el.value) });
    }
  }

  _onInput(e) {
    const el = e.target;
    if (el.dataset?.act === "search" && this._sheet?.type === "add") {
      this._sheet.query = el.value;
      clearTimeout(this._searchTimer);
      const q = el.value;
      this._searchTimer = setTimeout(() => this._doSearch(q), 400);
    } else if (el.dataset?.posinp && this._sheet?.type === "detail") {
      if (this._sheet.posStatus || this._sheet.posSaved) {
        this._sheet.posSaved = false;
        this._setPosStatus(null, "");
      }
    }
  }
}

const STYLES = `
:host { display:block; height:100%; }
* { box-sizing:border-box; }
button { font:inherit; color:inherit; cursor:pointer; -webkit-tap-highlight-color:transparent; }
.root {
  --bg: var(--primary-background-color, #fafafa);
  --card: var(--card-background-color, #fff);
  --card2: var(--secondary-background-color, #f2f2f2);
  --text: var(--primary-text-color, #212121);
  --muted: var(--secondary-text-color, #727272);
  --border: var(--divider-color, rgba(0,0,0,.12));
  --accent: var(--primary-color, #03a9f4);
  --on-accent: var(--text-primary-color, #fff);
  --radius: 16px;
  --shadow: var(--ha-card-box-shadow, 0 1px 3px rgba(0,0,0,.08));
  --font: var(--paper-font-body1_-_font-family, -apple-system, "Segoe UI", Roboto, "Noto Sans KR", sans-serif);
  --mono: ui-monospace, "SF Mono", "Roboto Mono", Menlo, monospace;
  --pos: #f04452; --neg: #3182f6;
  --bgimg: none;
  --blur: none;
  height:100%; display:flex; flex-direction:column; position:relative;
  background: var(--bg); background-image: var(--bgimg); background-attachment: fixed;
  color: var(--text); font-family: var(--font); font-size:15px; line-height:1.4;
}
.root.up-green { --pos: #12a150; --neg: #f04452; }
.root.up-red { --pos: #f04452; --neg: #3182f6; }

/* ---------- themes ---------- */
.t-midnight { --bg:#0b1220; --card:#131c2e; --card2:#1a2540; --text:#e6edf7; --muted:#8b9bb4; --border:#22304d; --accent:#4f8cff; --on-accent:#fff; --shadow:0 4px 18px rgba(0,0,0,.35); }
.t-paper { --bg:#f6f1e7; --card:#fffdf8; --card2:#f1ead9; --text:#2b2620; --muted:#7a6f60; --border:#e5dccb; --accent:#b5651d; --on-accent:#fff; --shadow:0 1px 0 #e5dccb; --font: Georgia, "Noto Serif KR", serif; }
.t-terminal { --bg:#050805; --card:#0a120a; --card2:#0f1c0f; --text:#b6f7b0; --muted:#5f9a5a; --border:#1c3a1c; --accent:#39ff14; --on-accent:#031003; --radius:3px; --shadow:none; --font: var(--mono); }
.t-neon { --bg:#0d0221; --card:#1a0b3d; --card2:#241252; --text:#f5e9ff; --muted:#a88bd6; --border:#3c1f7a; --accent:#ff2bd6; --on-accent:#fff; --shadow:0 0 0 1px #3c1f7a, 0 0 22px rgba(255,43,214,.15); }
.t-neon .chg.up, .t-neon .idx-c.up { text-shadow:0 0 10px var(--pos); }
.t-neon .chg.down, .t-neon .idx-c.down { text-shadow:0 0 10px var(--neg); }
.t-glass { --bg:#5b5fd6; --bgimg: linear-gradient(135deg,#667eea 0%,#764ba2 55%,#f093fb 100%); --card:rgba(255,255,255,.14); --card2:rgba(255,255,255,.2); --text:#fff; --muted:rgba(255,255,255,.75); --border:rgba(255,255,255,.28); --accent:#fff; --on-accent:#4b3fa8; --shadow:0 8px 30px rgba(31,38,135,.25); --blur: blur(14px) saturate(140%); }
.t-glass.up-red { --pos:#ffd1d6; --neg:#c9e3ff; }
.t-glass.up-green { --pos:#b9ffd6; --neg:#ffd1d6; }
.t-ocean { --bg:#e8f4f8; --card:#fff; --card2:#d9eef5; --text:#0b3a4a; --muted:#4f7d8c; --border:#cde5ec; --accent:#0096c7; --on-accent:#fff; }
.t-sunset { --bg:#fff1e6; --bgimg: linear-gradient(160deg,#fff1e6,#ffe3ec); --card:#fffaf6; --card2:#ffeee6; --text:#4a2328; --muted:#9b6b6f; --border:#f6d5cf; --accent:#ff6b35; --on-accent:#fff; --radius:20px; }
.t-forest { --bg:#0f1a14; --card:#16251c; --card2:#1d3225; --text:#e3f1e7; --muted:#8fb19b; --border:#24392c; --accent:#4caf7a; --on-accent:#08130c; --shadow:0 4px 14px rgba(0,0,0,.3); }
.t-mono { --bg:#fff; --card:#fff; --card2:#f4f4f4; --text:#111; --muted:#777; --border:#e3e3e3; --accent:#111; --on-accent:#fff; --radius:0; --shadow:none; }
.t-mono.up-red { --pos:#111; --neg:#888; }
.t-mono.up-green { --pos:#111; --neg:#888; }
.t-pastel { --bg:#f7f5ff; --card:#fff; --card2:#efebff; --text:#3d3a50; --muted:#8a86a3; --border:#ebe7fb; --accent:#9b8cff; --on-accent:#fff; --radius:22px; --shadow:0 6px 20px rgba(155,140,255,.12); }
.t-ink { --bg:#f3efe6; --card:#fbf8f1; --card2:#efe8da; --text:#1b1b1b; --muted:#6b665c; --border:#d9d1c0; --accent:#b3261e; --on-accent:#fff; --radius:6px; --shadow:none; --font: "Noto Serif KR", "Nanum Myeongjo", Georgia, serif; }
.t-amoled { --bg:#000; --card:#0a0a0a; --card2:#141414; --text:#f2f2f2; --muted:#8a8a8a; --border:#1c1c1c; --accent:#00d1ff; --on-accent:#001018; --shadow:none; }

/* ---------- shell ---------- */
header { display:flex; align-items:center; gap:8px; padding:10px 16px; padding-top:calc(10px + env(safe-area-inset-top, 0px));
  background: var(--app-header-background-color, var(--card)); color: var(--app-header-text-color, var(--text));
  border-bottom:1px solid var(--border); position:sticky; top:0; z-index:5; backdrop-filter: var(--blur); }
.t-glass header, .t-terminal header, .t-neon header, .t-midnight header, .t-forest header, .t-amoled header, .t-paper header, .t-ink header, .t-ocean header, .t-sunset header, .t-pastel header, .t-mono header { background: var(--card); color: var(--text); }
.brand { flex:1; min-width:0; }
.title { font-weight:700; font-size:18px; letter-spacing:-.01em; }
.sub { font-size:12px; color:var(--muted); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.actions { display:flex; gap:6px; align-items:center; }
.icon-btn { min-width:40px; height:40px; border-radius:12px; border:1px solid var(--border); background:var(--card); font-size:18px; display:inline-flex; align-items:center; justify-content:center; }
.icon-btn.sm { min-width:32px; height:32px; font-size:13px; border-radius:9px; }
.icon-btn.danger { color:#e5484d; }
.icon-btn:disabled { opacity:.35; cursor:default; }
.pill-btn { height:40px; min-width:44px; padding:0 12px; border-radius:20px; border:1px solid var(--border); background:var(--card); font-weight:700; font-size:13px; }
.tabs { display:flex; gap:4px; }
.tabs.top { padding:8px 16px 0; max-width:1200px; width:100%; margin:0 auto; }
.tabs.bottom { display:none; }
.tab { flex:0 0 auto; border:1px solid var(--border); background:var(--card); border-radius:999px; padding:7px 14px; font-size:14px; display:flex; gap:6px; align-items:center; }
.tab.on { background:var(--accent); color:var(--on-accent); border-color:transparent; }
.scroller { flex:1; overflow-y:auto; -webkit-overflow-scrolling:touch; overscroll-behavior:contain; }
main { max-width:1200px; margin:0 auto; padding:8px 16px 24px; }
.bottom-pad { height:24px; }
.add-btn { height:40px; padding:0 14px 0 10px; border-radius:20px; border:none; background:var(--accent); color:var(--on-accent); font-weight:700; font-size:14px; display:inline-flex; align-items:center; gap:4px; box-shadow:0 2px 8px rgba(0,0,0,.15); }
.add-btn .plus { font-size:20px; line-height:1; }
.root.narrow .add-btn { width:40px; padding:0; justify-content:center; }
.root.narrow .add-btn .add-l { display:none; }

/* narrow / mobile */
.root.narrow .tabs.top { display:none; }
.root.narrow .tabs.bottom { display:flex; position:relative; z-index:5; background:var(--card); border-top:1px solid var(--border);
  padding:4px 4px calc(4px + env(safe-area-inset-bottom, 0px)); backdrop-filter: var(--blur); }
.root.narrow .tabs.bottom .tab { flex:1; flex-direction:column; gap:1px; border:none; background:none; border-radius:12px; padding:6px 2px; font-size:11px; }
.root.narrow .tabs.bottom .tab .ti { font-size:19px; filter: grayscale(.6); }
.root.narrow .tabs.bottom .tab.on { color:var(--accent); background:var(--card2); }
.root.narrow .tabs.bottom .tab.on .ti { filter:none; }
.root.narrow main { padding:6px 12px 90px; }
.root.narrow header { padding-left:8px; padding-right:10px; }

/* ---------- sections ---------- */
.sec { margin-top:18px; }
.sec-h { display:flex; align-items:center; justify-content:space-between; margin:0 2px 8px; }
.sec-h h2 { font-size:16px; margin:0; font-weight:700; }
.link-btn { border:none; background:none; color:var(--accent); font-weight:600; padding:6px 4px; }
.banner { margin-top:12px; padding:10px 14px; border-radius:12px; background:var(--card2); font-size:14px; }
.banner.subtle { font-size:12.5px; color:var(--muted); }
.empty { padding:18px; border-radius:var(--radius); background:var(--card); border:1px dashed var(--border); color:var(--muted); font-size:14px; display:flex; flex-direction:column; gap:10px; }
.empty.big { margin-top:40px; text-align:center; font-size:15px; }
.mono { font-family: var(--mono); font-variant-numeric: tabular-nums; letter-spacing:-.02em; }
.muted { color:var(--muted); }
.small { font-size:12.5px; }
.up { color:var(--pos); } .down { color:var(--neg); } .flat { color:var(--muted); }

.chips { display:flex; flex-wrap:wrap; gap:8px; }
.chip { display:inline-flex; align-items:center; gap:8px; padding:9px 12px; border-radius:12px; background:var(--card); border:1px solid var(--border); box-shadow:var(--shadow); font-size:13.5px; backdrop-filter: var(--blur); }
.chip b { font-weight:600; }
.chip .dot { width:8px; height:8px; border-radius:50%; background:var(--muted); }
.chip.sess.open .dot { background:#22c55e; box-shadow:0 0 0 3px rgba(34,197,94,.2); }
.hero { padding:16px 18px; border-radius:var(--radius); background:var(--card); border:1px solid var(--border); box-shadow:var(--shadow); margin-bottom:10px; backdrop-filter: var(--blur); }
.hero-l { font-size:13px; color:var(--muted); }
.hero-v { font-size:30px; font-weight:800; margin:2px 0; }
.hero-c { font-size:15px; font-weight:600; }

.hscroll { display:flex; gap:10px; overflow-x:auto; scroll-snap-type:x mandatory; padding:2px 2px 8px; margin:0 -2px; scrollbar-width:thin; }
.idx { flex:0 0 auto; min-width:150px; scroll-snap-align:start; text-align:left; border:1px solid var(--border); background:var(--card); border-radius:var(--radius); padding:12px 14px 8px; box-shadow:var(--shadow); backdrop-filter: var(--blur); }
.idx-top { font-size:13px; color:var(--muted); }
.idx-v { font-size:19px; font-weight:700; margin-top:2px; }
.idx-c { font-size:13px; font-weight:600; }
.spark { display:block; width:100%; height:28px; margin-top:6px; }
.spark.up { color:var(--pos); } .spark.down { color:var(--neg); }
.spark.wide { height:40px; }
.spark-ph { height:28px; }
.spark-ph.wide { height:40px; }

/* ---------- item grid / layouts ---------- */
.grid { display:grid; gap:10px; }
.item { position:relative; background:var(--card); border:1px solid var(--border); border-radius:var(--radius); box-shadow:var(--shadow); overflow:hidden; backdrop-filter: var(--blur); }
.item .hit { display:block; width:100%; text-align:left; border:none; background:none; padding:12px 14px; min-height:48px; }
.item .hit:active { background:var(--card2); }
.av { --h:200; width:36px; height:36px; flex:0 0 36px; border-radius:50%; display:inline-flex; align-items:center; justify-content:center; font-weight:700; font-size:12px;
  background:hsl(var(--h) 70% 92%); color:hsl(var(--h) 55% 32%); }
.t-midnight .av, .t-terminal .av, .t-neon .av, .t-forest .av, .t-amoled .av, .t-glass .av { background:hsl(var(--h) 45% 26%); color:hsl(var(--h) 85% 85%); }
.nm { display:flex; flex-direction:column; min-width:0; }
.nm b { font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.badge { display:inline-block; font-size:11.5px; color:var(--muted); background:var(--card2); border-radius:6px; padding:1px 6px; margin:2px 4px 0 0; width:fit-content; font-family:var(--mono); }
.badge.warn { color:#b7791f; }
.row { display:flex; gap:10px; align-items:center; }
.row2 { display:flex; justify-content:space-between; align-items:baseline; margin-top:8px; gap:8px; flex-wrap:wrap; }
.row3 { margin-top:2px; }
.px { font-size:18px; font-weight:700; }
.chg { font-size:13.5px; font-weight:600; }
.krw { font-size:12px; color:var(--muted); }
.edit-row { display:flex; gap:6px; justify-content:flex-end; padding:0 10px 10px; }

.layout-cards .grid { grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); }
.layout-list .grid { grid-template-columns: 1fr; gap:0; border-radius:var(--radius); overflow:hidden; border:1px solid var(--border); background:var(--card); box-shadow:var(--shadow); }
.layout-list .item, .layout-tape .grid .item { border:none; border-radius:0; box-shadow:none; border-bottom:1px solid var(--border); background:transparent; }
.layout-list .item:last-child { border-bottom:none; }
.item.list .hit { display:flex; align-items:center; gap:12px; }
.item.list .nm { flex:1; }
.item.list .sp { width:80px; flex:0 0 80px; }
.item.list .sp .spark { margin:0; }
.item.list .rt { display:flex; flex-direction:column; align-items:flex-end; }
.item.list .px { font-size:16px; }
.layout-compact .grid { grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap:8px; }
.item.compact .hit { display:flex; flex-direction:column; gap:2px; padding:10px 12px; }
.nm1 { font-weight:600; font-size:13.5px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.item.compact .px { font-size:16px; }
.layout-big .grid { grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); }
.item.big .hit { padding:16px 18px; }
.bigpx { font-size:34px; font-weight:800; margin-top:10px; letter-spacing:-.03em; }
.item.big .row2 { margin-top:2px; justify-content:flex-start; gap:12px; }
.item.big .spark.wide { height:60px; }
.layout-heatmap .grid { grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap:6px; }
.item.heat { border:none; }
.item.heat.d-up { background: color-mix(in srgb, var(--pos) calc(var(--mag) * 100%), var(--card)); }
.item.heat.d-down { background: color-mix(in srgb, var(--neg) calc(var(--mag) * 100%), var(--card)); }
.item.heat .hit { display:flex; flex-direction:column; align-items:center; text-align:center; padding:12px 6px; min-height:92px; justify-content:center; gap:2px; }
.item.heat .nm1 { max-width:100%; }
.item.heat .heat-pct { font-size:20px; font-weight:800; }
.item.heat .heat-px { font-size:12px; opacity:.85; }
.item.heat.d-up .hit, .item.heat.d-down .hit { color: var(--text); }
.tape { overflow:hidden; border-radius:var(--radius); background:var(--card); border:1px solid var(--border); box-shadow:var(--shadow); }
.tape-track { display:flex; width:max-content; }
.tape.anim .tape-track { animation: tape 40s linear infinite; }
.tape.anim:hover .tape-track { animation-play-state: paused; }
@keyframes tape { from { transform:translateX(0); } to { transform:translateX(-50%); } }
.tape-item { display:inline-flex; gap:8px; align-items:baseline; white-space:nowrap; padding:14px 18px; border:none; background:none; border-right:1px solid var(--border); }
@media (prefers-reduced-motion: reduce) { .tape { overflow-x:auto; } .tape.anim .tape-track { animation:none; } }

/* ---------- portfolio ---------- */
.pf-head { display:grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap:12px; padding:14px 16px; border-radius:var(--radius); background:var(--card); border:1px solid var(--border); box-shadow:var(--shadow); margin-bottom:10px; backdrop-filter: var(--blur); }
.pf-v { font-size:20px; font-weight:800; }
.alloc { display:flex; height:12px; border-radius:6px; overflow:hidden; margin:6px 0; gap:2px; }
.alloc span { --h:200; background:hsl(var(--h) 65% 55%); min-width:3px; }
.alloc-legend { display:flex; flex-wrap:wrap; gap:6px 12px; font-size:12px; color:var(--muted); margin-bottom:10px; }
.alloc-legend i { --h:200; display:inline-block; width:8px; height:8px; border-radius:2px; background:hsl(var(--h) 65% 55%); margin-right:5px; }
.pf-list { border-radius:var(--radius); overflow:hidden; border:1px solid var(--border); background:var(--card); box-shadow:var(--shadow); }
.pf-row { width:100%; display:flex; justify-content:space-between; gap:10px; align-items:center; text-align:left; border:none; background:none; border-bottom:1px solid var(--border); padding:12px 14px; min-height:56px; }
.pf-row:last-child { border-bottom:none; }
.pf-row .rt { display:flex; flex-direction:column; align-items:flex-end; }
.pf-row.pf-hit { background:color-mix(in srgb, var(--accent) 8%, transparent); }
.alert-badge { display:inline-block; margin-top:4px; padding:2px 7px; border-radius:6px; font-size:11.5px; font-family:var(--mono); color:var(--muted); background:var(--card2); width:fit-content; }
.alert-badge.hit { font-weight:700; border:1px solid currentColor; background:color-mix(in srgb, currentColor 12%, transparent); }
.alert-banner { padding:9px 12px; border-radius:10px; font-size:13.5px; font-weight:700; margin-bottom:8px; border:1px solid currentColor; background:color-mix(in srgb, currentColor 12%, transparent); }
.alert-box { margin-top:8px; padding:10px 12px; border-radius:12px; background:var(--card2); border:1px solid var(--border); }

/* ---------- disclosures ---------- */
.disc { border-radius:var(--radius); overflow:hidden; border:1px solid var(--border); background:var(--card); box-shadow:var(--shadow); }
.disc-row { display:flex; gap:12px; align-items:center; padding:12px 14px; border-bottom:1px solid var(--border); color:inherit; text-decoration:none; min-height:52px; }
.disc-row:last-child { border-bottom:none; }
.disc-d { color:var(--muted); font-size:13px; flex:0 0 42px; }
.disc-t { flex:1; display:flex; flex-direction:column; min-width:0; }
.disc-t span { font-size:13.5px; color:var(--muted); overflow:hidden; text-overflow:ellipsis; }

/* ---------- sheet ---------- */
.backdrop { position:fixed; inset:0; background:rgba(0,0,0,.42); z-index:20; animation: fade .15s ease; }
.sheet { position:fixed; z-index:21; top:0; right:0; bottom:0; width:min(460px, 100%); background:var(--card); color:var(--text); display:flex; flex-direction:column; box-shadow:-10px 0 40px rgba(0,0,0,.2); animation: slidein .2s ease; }
.t-glass .sheet { background:#4c4aa8; }
.grab { display:none; }
.sheet-h { display:flex; align-items:center; justify-content:space-between; padding:14px 16px; border-bottom:1px solid var(--border); gap:8px; }
.sheet-h h3 { margin:0; font-size:18px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.sheet-b { flex:1; overflow-y:auto; padding:8px 16px calc(24px + env(safe-area-inset-bottom, 0px)); -webkit-overflow-scrolling:touch; overscroll-behavior:contain; }
.sheet-b h4 { margin:20px 0 8px; font-size:14px; color:var(--muted); font-weight:600; }
@keyframes fade { from { opacity:0; } }
@keyframes slidein { from { transform:translateX(30px); opacity:0; } }
@keyframes slideup { from { transform:translateY(40px); opacity:.4; } }
.noanim { animation:none !important; }
.root.narrow .sheet { top:auto; left:0; width:100%; max-height:92vh; border-radius:20px 20px 0 0; animation: slideup .22s ease; box-shadow:0 -10px 40px rgba(0,0,0,.25); }
.root.narrow .grab { display:block; width:40px; height:5px; border-radius:3px; background:var(--border); margin:8px auto 0; }

.seg { display:flex; flex-wrap:wrap; gap:6px; }
.seg button { border:1px solid var(--border); background:var(--card2); border-radius:10px; padding:9px 12px; font-size:13.5px; min-height:40px; }
.seg button.on { background:var(--accent); color:var(--on-accent); border-color:transparent; font-weight:600; }
.seg.wide { display:grid; grid-template-columns: repeat(auto-fit, minmax(60px, 1fr)); margin:8px 0; }
.theme-grid { display:grid; grid-template-columns: repeat(auto-fill, minmax(96px, 1fr)); gap:8px; }
.theme { border:2px solid var(--border); background:var(--card2); border-radius:12px; padding:8px; display:flex; flex-direction:column; align-items:center; gap:6px; font-size:12.5px; }
.theme.on { border-color:var(--accent); }
.sw { position:relative; width:100%; height:38px; border-radius:8px; border:1px solid rgba(0,0,0,.1); }
.sw i { position:absolute; right:6px; bottom:6px; width:12px; height:12px; border-radius:50%; }
.lay { font-size:22px; height:38px; display:flex; align-items:center; }
.sec-list { border:1px solid var(--border); border-radius:12px; overflow:hidden; }
.sec-row { display:flex; justify-content:space-between; align-items:center; padding:6px 10px; border-bottom:1px solid var(--border); }
.sec-row:last-child { border-bottom:none; }
.sw-row { display:flex; gap:10px; align-items:center; min-height:44px; cursor:pointer; }
.sw-row input { width:20px; height:20px; accent-color: var(--accent); }
.field { margin:10px 0; display:flex; flex-direction:column; gap:6px; }
.field > span, .field label > span { font-size:13px; color:var(--muted); }
.field.inline { flex-direction:row; justify-content:space-between; align-items:center; }
.field.two { display:grid; grid-template-columns: 1fr 1fr; gap:10px; }
.field label { display:flex; flex-direction:column; gap:6px; }
.inp, select { width:100%; min-height:46px; border-radius:12px; border:1px solid var(--border); background:var(--card2); color:var(--text); padding:10px 12px; font-size:16px; }
.inp:focus, select:focus { outline:2px solid var(--accent); outline-offset:0; }
.results { display:flex; flex-direction:column; gap:4px; max-height:240px; overflow-y:auto; }
.res { display:flex; gap:8px; align-items:center; text-align:left; border:1px solid var(--border); background:var(--card2); border-radius:10px; padding:10px 12px; min-height:46px; }
.res-n { flex:1; min-width:0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.pad { padding:8px 4px; }
.lookup-box { padding:10px 12px; border-radius:12px; background:var(--card2); border:1px solid var(--border); margin:6px 0 10px; }
.lookup-h { font-size:12px; color:var(--muted); font-weight:600; margin-bottom:6px; }
.lookup-links { display:flex; flex-wrap:wrap; gap:6px; }
.lookup-link { display:inline-flex; align-items:center; gap:4px; padding:6px 10px; border-radius:8px; border:1px solid var(--border); background:var(--card); color:var(--accent); font-size:12.5px; font-weight:600; text-decoration:none; }
.lookup-link:hover { border-color:var(--accent); }
.cat-tabs { display:flex; gap:6px; overflow-x:auto; padding:2px 0 8px; scrollbar-width:thin; }
.cat-tab { flex:0 0 auto; border:1px solid var(--border); background:var(--card2); border-radius:999px; padding:6px 12px; font-size:12.5px; white-space:nowrap; }
.cat-tab.on { background:var(--accent); color:var(--on-accent); border-color:transparent; font-weight:600; }
.cat-list { display:flex; flex-direction:column; gap:4px; max-height:280px; overflow-y:auto; border:1px solid var(--border); border-radius:12px; padding:6px; background:var(--card2); }
.cat-row { display:flex; align-items:center; gap:6px; background:var(--card); border:1px solid var(--border); border-radius:10px; padding:4px 6px 4px 10px; min-height:46px; }
.cat-pick { flex:1; min-width:0; display:flex; align-items:center; gap:8px; text-align:left; border:none; background:none; padding:4px 0; }
.cat-add-btn { flex:0 0 auto; border:none; border-radius:8px; background:var(--accent); color:var(--on-accent); font-size:12.5px; font-weight:600; padding:7px 11px; min-height:34px; white-space:nowrap; }
.cat-add-btn:disabled { opacity:.5; }
.cat-added { flex:0 0 auto; font-size:12px; font-weight:600; color:var(--muted); padding:6px 8px; white-space:nowrap; }
.direct-box { margin-top:14px; padding-top:12px; border-top:1px solid var(--border); }
.quick { display:flex; gap:6px; flex-wrap:wrap; }
.chip-btn { border:1px solid var(--border); background:var(--card2); border-radius:999px; padding:8px 14px; font-family:var(--mono); font-weight:600; min-height:40px; }
.btn-row { display:flex; gap:8px; justify-content:flex-end; margin-top:14px; flex-wrap:wrap; }
.btn { min-height:46px; padding:0 18px; border-radius:12px; border:1px solid var(--border); background:var(--card2); font-weight:600; }
.btn.sm { min-height:38px; padding:0 14px; }
.btn.primary { background:var(--accent); color:var(--on-accent); border-color:transparent; }
.btn.saved { background:#12a150; color:#fff; border-color:transparent; }
.btn.danger { color:#e5484d; }
.pos-status { margin-top:10px; padding:10px 12px; border-radius:10px; font-size:13.5px; font-weight:600; }
.pos-status[hidden] { display:none; }
.pos-status.ok { background:rgba(18,161,80,.14); color:#12a150; border:1px solid rgba(18,161,80,.45); }
.pos-status.err { background:rgba(229,72,77,.14); color:#e5484d; border:1px solid rgba(229,72,77,.45); }
.armed { background:#e5484d !important; color:#fff !important; border-color:transparent !important; }
.btn:disabled { opacity:.6; }
.err { color:#e5484d; font-size:13.5px; margin-top:6px; }
.err[hidden] { display:none; }

.d-top { padding:6px 0 4px; }
.d-px { font-size:34px; font-weight:800; margin-top:6px; letter-spacing:-.03em; }
.d-chg { font-size:15px; font-weight:600; }
.chart-wrap { position:relative; margin:8px 0 4px; touch-action: pan-y; }
.chart-wrap.up { color:var(--pos); } .chart-wrap.down { color:var(--neg); }
.chart { width:100%; height:220px; display:block; }
.chart .xh { stroke: var(--muted); }
.chart .xd { fill: currentColor; stroke: var(--card); stroke-width:2; }
.chart-lbl { position:absolute; transform:translateX(-50%); font-size:11px; color:var(--muted); font-family:var(--mono); pointer-events:none; white-space:nowrap; }
.chart-lbl.max { top:0; } .chart-lbl.min { bottom:20px; }
.chart-axis { display:flex; justify-content:space-between; font-size:11.5px; color:var(--muted); }
.chart-tip { position:absolute; top:-6px; transform:translateX(-50%); background:var(--text); color:var(--card); padding:5px 9px; border-radius:8px; font-size:12px; pointer-events:none; white-space:nowrap; text-align:center; font-family:var(--mono); }
.chart-tip .up, .chart-tip .down { color:inherit; opacity:.85; }
.chart-msg { height:220px; display:flex; align-items:center; justify-content:center; color:var(--muted); font-size:14px; }
.range { display:flex; align-items:center; gap:8px; margin:4px 0 10px; }
.range-bar { flex:1; height:6px; border-radius:3px; background:linear-gradient(90deg, var(--neg), var(--muted), var(--pos)); position:relative; opacity:.8; }
.range-bar i { position:absolute; top:-4px; width:4px; height:14px; border-radius:2px; background:var(--text); transform:translateX(-50%); }
.stats { display:grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap:8px; margin-top:8px; }
.stat { background:var(--card2); border-radius:10px; padding:8px 10px; display:flex; flex-direction:column; font-size:13px; }
.pos-sum { font-size:15px; margin-bottom:4px; }

.toast { position:absolute; left:50%; bottom:28px; transform:translate(-50%, 20px); background:var(--text); color:var(--card); padding:10px 16px; border-radius:12px; font-size:14px; opacity:0; pointer-events:none; transition: all .2s ease; z-index:30; max-width:90%; text-align:center; }
.toast.show { opacity:1; transform:translate(-50%, 0); }
.root.narrow .toast { bottom:calc(90px + env(safe-area-inset-bottom, 0px)); }

@media (max-width: 600px) {
  .layout-cards .grid { grid-template-columns: 1fr 1fr; gap:8px; }
  .layout-cards .item .hit { padding:10px 12px; }
  .layout-cards .px { font-size:16px; }
  .layout-cards .av { display:none; }
  .layout-compact .grid { grid-template-columns: 1fr 1fr; }
  .layout-heatmap .grid { grid-template-columns: repeat(3, 1fr); }
  .layout-big .grid { grid-template-columns: 1fr; }
  .item.list .sp { width:56px; flex-basis:56px; }
  .idx { min-width:132px; }
  .hero-v { font-size:26px; }
  .field.two { grid-template-columns: 1fr; }
}
@media (max-width: 360px) {
  .layout-cards .grid { grid-template-columns: 1fr; }
  .layout-heatmap .grid { grid-template-columns: 1fr 1fr; }
  .item.list .sp { display:none; }
}
`;

if (!customElements.get("kr-finance-panel")) {
  customElements.define("kr-finance-panel", KRFinancePanel);
}
