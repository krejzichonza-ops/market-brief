#!/usr/bin/env python3
"""
Morning Brief Generator v2 — rozšířená analýza
09:15 ET každý pracovní den via GitHub Actions.
"""

import anthropic, json, os, re, sys
from datetime import datetime
import pytz

ET = pytz.timezone('America/New_York')
now_et = datetime.now(ET)
DATE_KEY = now_et.strftime('%Y-%m-%d')
DATE_STR = now_et.strftime('%A, %B %d, %Y')
DOW = now_et.strftime('%A')  # Monday, Tuesday...
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
os.makedirs(DATA_DIR, exist_ok=True)
OUTPUT_FILE = os.path.join(DATA_DIR, f'{DATE_KEY}.json')

PORTFOLIO_FILE = os.path.join(DATA_DIR, 'portfolio.json')

def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, 'r') as f:
            return json.load(f)
    return {
        "starting_capital": 100000.0,
        "current_capital": 100000.0,
        "peak_capital": 100000.0,
        "total_trades": 0,
        "winning_trades": 0,
        "losing_trades": 0,
        "equity_curve": [{"date": DATE_KEY, "value": 100000.0, "note": "Starting capital"}],
        "open_positions": [],
        "closed_trades": []
    }

portfolio = load_portfolio()
current_capital = portfolio["current_capital"]
open_positions = portfolio.get("open_positions", [])

if os.path.exists(OUTPUT_FILE):
    existing = json.load(open(OUTPUT_FILE))
    if existing.get('brief'):
        print(f"✓ Morning brief pro {DATE_KEY} již existuje, přeskakuji.")
        sys.exit(0)

open_pos_str = "none"
if open_positions:
    open_pos_str = json.dumps(open_positions, ensure_ascii=False)

client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])

SYSTEM_PROMPT = f"""You are a professional US equity portfolio manager AND market analyst with web search access. Today is {DATE_STR} ({DOW}).

PORTFOLIO STATUS:
- Available capital for new trades: ${current_capital:,.2f}
- Currently open positions (may be multi-day holds): {open_pos_str}

STEP 1 — MARKET DATA (search for all of these):
- US futures: S&P 500, Nasdaq, Dow — current levels and % change
- VIX current level (critical for position sizing and probability estimates)
- 10Y UST yield, DXY, crude oil, gold
- After-hours and pre-market movers with specific % moves and reasons
- Key macro events today and this week (Fed speakers, CPI, jobs, PMI, GDP)
- Geopolitical developments affecting markets

STEP 2 — ADVANCED MARKET CONTEXT (search for each):
- Options flow: put/call ratio on S&P 500 and any high-conviction pick tickers (unusual options activity = institutional signal)
- Short interest: for each potential pick, what is the % float short? High short interest + catalyst = squeeze potential
- Insider trading: any SEC Form 4 filings in last 48 hours for potential picks (insider buying is bullish signal)
- Earnings calendar: which companies report earnings in next 5 trading days? This affects volatility and sector moves
- Volume analysis: is today's pre-market volume above or below 20-day average? Thin markets = higher risk

STEP 3 — PICK SELECTION with CORRELATION CHECK:
Select 1-5 picks. CRITICAL: before finalizing, check that picks are NOT highly correlated.
- Do NOT pick 2+ stocks from same sub-sector (e.g. two oil majors, two semiconductors)
- Do NOT pick both an ETF and its major component (e.g. XLE + CVX)
- Each pick must represent a DIFFERENT thesis / exposure
- If you cannot find 5 truly uncorrelated setups today, pick fewer — quality over quantity

ALLOCATION RULES:
- Total capital: ${current_capital:,.2f}
- Size by conviction: high conviction = larger position, low conviction = smaller
- MINIMUM TARGET: ≥3% from entry (ideally 5%+)
- Stop loss: based on real technical levels, not tighter than 1% from entry
- Holding days: 1-3 trading days maximum

THESIS REQUIREMENTS for every pick:
1. thesis_macro: Macro environment support for this specific trade
2. thesis_technical: Exact technical setup — pattern, key S/R levels, moving averages, volume
3. thesis_catalyst: Specific near-term catalyst (be precise — what event, when)
4. thesis_options: Options flow / put-call ratio insight for this ticker (if available)
5. thesis_short_interest: Short interest % float and what it means for this trade
6. thesis_insider: Any recent insider activity? If none found, state "No recent insider filings"
7. thesis_volume: Is volume confirming the setup? Above/below average?
8. thesis_correlation: Why this pick is NOT correlated with the other picks today
9. thesis_risk: Main risk that could invalidate the thesis
10. entry_logic: Exactly why this entry price — what level, why here
11. exit_logic: Why this target is achievable — what resistance/support justifies it
12. probability_pct: Honest probability 0-100 that price hits target within holding_days
    - Account for: VIX level, catalyst strength, technical clarity, short interest, options flow
    - Ranges: weak 35-45%, solid 50-65%, high-conviction 65-80%
13. probability_reasoning: What specific factors pushed probability up or down

Return ONLY valid JSON:
{{
  "generated_at": "ISO timestamp",
  "market_date": "{DATE_STR}",
  "date_key": "{DATE_KEY}",
  "day_of_week": "{DOW}",
  "snapshot": {{
    "sp500_futures": "value+%", "nasdaq_futures": "value+%", "dow_futures": "value+%",
    "vix": "value", "us10y": "yield%", "dxy": "value", "crude_oil": "price", "gold": "price"
  }},
  "market_context": {{
    "vix_regime": "low|normal|elevated|high",
    "options_pcr": "put/call ratio value or 'unavailable'",
    "market_volume": "above_average|average|below_average",
    "earnings_this_week": ["TICKER: date", "TICKER: date"],
    "insider_activity_summary": "Any notable insider buys/sells across market today"
  }},
  "overall_sentiment": "bullish|neutral|bearish",
  "sentiment_score": 0-100,
  "key_themes": ["theme1","theme2","theme3"],
  "macro_summary": "2-3 paragraphs",
  "afterhours_summary": "2-3 paragraphs",
  "geopolitical_summary": "1-2 paragraphs",
  "sectors": [
    {{"name":"Technology","signal":"bullish|neutral|bearish","score":0-100,"reason":""}},
    {{"name":"Financials","signal":"bullish|neutral|bearish","score":0-100,"reason":""}},
    {{"name":"Energy","signal":"bullish|neutral|bearish","score":0-100,"reason":""}},
    {{"name":"Consumer Discretionary","signal":"bullish|neutral|bearish","score":0-100,"reason":""}},
    {{"name":"Healthcare","signal":"bullish|neutral|bearish","score":0-100,"reason":""}},
    {{"name":"Industrials","signal":"bullish|neutral|bearish","score":0-100,"reason":""}},
    {{"name":"Utilities","signal":"bullish|neutral|bearish","score":0-100,"reason":""}}
  ],
  "picks": [
    {{
      "ticker": "AAPL",
      "company": "Apple Inc.",
      "direction": "long|short",
      "entry_price": 0.00,
      "target_price": 0.00,
      "stop_loss": 0.00,
      "target_pct": 0.0,
      "stop_pct": 0.0,
      "position_size_usd": 20000.00,
      "holding_days": 1,
      "risk_reward": "1:2.0",
      "confidence": "high|medium|low",
      "thesis_macro": "...",
      "thesis_technical": "...",
      "thesis_catalyst": "...",
      "thesis_options": "Put/call ratio and unusual options activity",
      "thesis_short_interest": "Short interest % float and squeeze potential",
      "thesis_insider": "Recent insider filings or 'No recent insider filings'",
      "thesis_volume": "Volume vs 20-day average and what it signals",
      "thesis_correlation": "Why this pick is uncorrelated with the other picks today",
      "thesis_risk": "...",
      "entry_logic": "...",
      "exit_logic": "...",
      "probability_pct": 60,
      "probability_reasoning": "...",
      "catalysts": ["catalyst1", "catalyst2"]
    }}
  ],
  "portfolio_correlation_note": "Explanation of how today's picks are diversified across different exposures",
  "positions_to_close": ["TICKER1"],
  "portfolio_note": "Brief portfolio management reasoning",
  "risks": ["risk1","risk2","risk3"],
  "data_freshness": "note on data freshness"
}}
Picks: 1-5 stocks/ETFs. REAL prices. Target ≥3%. Total position_size_usd ≤ ${current_capital:,.2f}."""

USER_PROMPT = f"Generate morning brief for {DATE_STR}. Search all required data including options flow, short interest, insider filings, earnings calendar. Return only JSON."

print(f"🔍 Generuji morning brief pro {DATE_STR} ({DOW}) | Kapitál: ${current_capital:,.2f}")

response = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=8000,
    system=SYSTEM_PROMPT,
    tools=[{"type": "web_search_20250305", "name": "web_search"}],
    messages=[{"role": "user", "content": USER_PROMPT}]
)

raw_text = ''.join(b.text for b in response.content if hasattr(b, 'text'))

def extract_json(text):
    text = re.sub(r'```json\s*', '', text).replace('```', '').strip()
    start = min(text.find('{') if '{' in text else len(text),
                text.find('[') if '[' in text else len(text))
    return json.loads(text[start:])

try:
    brief_data = extract_json(raw_text)
except json.JSONDecodeError as e:
    print(f"❌ JSON parse error: {e}\n{raw_text[:300]}")
    sys.exit(1)

record = {
    "date": DATE_KEY,
    "brief": brief_data,
    "review": None,
    "reviewed": False,
    "created_at": datetime.utcnow().isoformat()
}

with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    json.dump(record, f, ensure_ascii=False, indent=2)

print(f"✅ Morning brief uložen | Sentiment: {brief_data.get('overall_sentiment')} | Picks: {', '.join(p['ticker'] for p in brief_data.get('picks', []))}")
