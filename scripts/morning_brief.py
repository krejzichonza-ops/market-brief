#!/usr/bin/env python3
"""
Morning Brief Generator — s portfolio alokací
09:15 ET každý pracovní den via GitHub Actions.
"""

import anthropic, json, os, re, sys
from datetime import datetime
import pytz

ET = pytz.timezone('America/New_York')
now_et = datetime.now(ET)
DATE_KEY = now_et.strftime('%Y-%m-%d')
DATE_STR = now_et.strftime('%A, %B %d, %Y')
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
os.makedirs(DATA_DIR, exist_ok=True)
OUTPUT_FILE = os.path.join(DATA_DIR, f'{DATE_KEY}.json')

# ── Načti předchozí portfolio hodnotu ────────────────────────────────────────
PORTFOLIO_FILE = os.path.join(DATA_DIR, 'portfolio.json')

def load_portfolio():
    """Načte aktuální stav portfolia. Pokud neexistuje, inicializuje 100 000 USD."""
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
        "equity_curve": [
            {"date": DATE_KEY, "value": 100000.0, "note": "Starting capital"}
        ],
        "open_positions": [],   # pozice přecházející přes den
        "closed_trades": []
    }

portfolio = load_portfolio()
current_capital = portfolio["current_capital"]
open_positions = portfolio.get("open_positions", [])

# Přeskoč pokud morning brief pro dnešek už existuje
if os.path.exists(OUTPUT_FILE):
    existing = json.load(open(OUTPUT_FILE))
    if existing.get('brief'):
        print(f"✓ Morning brief pro {DATE_KEY} již existuje, přeskakuji.")
        sys.exit(0)

# ── Připravu kontext otevřených pozic pro Claude ─────────────────────────────
open_pos_str = "none"
if open_positions:
    open_pos_str = json.dumps(open_positions, ensure_ascii=False)

client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])

SYSTEM_PROMPT = f"""You are a professional US equity portfolio manager AND market analyst with web search access. Today is {DATE_STR}.

PORTFOLIO STATUS:
- Available capital for new trades: ${current_capital:,.2f}
- Currently open positions (may be multi-day holds): {open_pos_str}

Your job:
1. Search for REAL current market data (futures, AH movers, macro, geopolitical)
2. Decide which of any open positions to CLOSE today vs HOLD further
3. Allocate available capital into up to 5 new positions for today/next 1-3 days
4. Each pick can have a holding horizon of 1, 2, or 3 trading days

ALLOCATION RULES:
- Total capital to deploy: ${current_capital:,.2f}
- Divide across 1-5 picks (not necessarily equal — size by conviction)
- Each pick needs: entry price, stop loss, take profit, holding_days (1-3), position size in USD
- For LONG: profit if price rises. For SHORT: profit if price falls (you short-sell).
- MINIMUM TARGET: take profit must be at least 3% away from entry (ideally 5%+). Only enter if the setup genuinely supports this — if not, skip that stock.
- Stop loss must be meaningful but not tighter than 1% from entry (avoid noise stop-outs).
- Stop loss and take profit must be based on real technical levels: recent support/resistance, ATR, key moving averages, earnings gaps, etc.

THESIS REQUIREMENTS — for every pick you MUST provide:
1. thesis_macro: How does today's macro environment support this trade? (Fed stance, rates, sector rotation, risk-on/off)
2. thesis_technical: What is the technical setup? (price level, pattern, key S/R, moving averages, volume, momentum)
3. thesis_catalyst: What specific near-term catalyst drives the expected move? (earnings, product launch, data release, options expiry, sector news)
4. thesis_risk: What is the main risk that could invalidate this thesis?
5. entry_logic: Exactly why this specific entry price (limit/market, what level, why here)?
6. exit_logic: Exactly why this specific target — what level, what resistance/support, why 3-5%+ is achievable?
7. probability_pct: Your honest estimated probability (0-100) that price hits the target within holding_days.
   - Be well-calibrated: if you say 70%, roughly 70% of such trades should succeed over time.
   - Account for: catalyst strength, technical clarity, macro alignment, holding period, VIX level.
   - Typical ranges: weak setup 35-45%, solid setup 50-65%, high-conviction 65-80%. Avoid extremes (>85% or <30%) unless truly exceptional.
8. probability_reasoning: 1-2 sentences explaining what specific factors pushed this probability estimate higher or lower.

Return ONLY valid JSON:
{{
  "generated_at": "ISO timestamp",
  "market_date": "{DATE_STR}",
  "date_key": "{DATE_KEY}",
  "snapshot": {{
    "sp500_futures": "value+%", "nasdaq_futures": "value+%", "dow_futures": "value+%",
    "vix": "value", "us10y": "yield%", "dxy": "value", "crude_oil": "price", "gold": "price"
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
      "thesis_macro": "How macro conditions support this specific trade today",
      "thesis_technical": "Specific technical setup: price pattern, key levels, indicators",
      "thesis_catalyst": "Specific near-term catalyst driving the expected move",
      "thesis_risk": "Main risk that could invalidate the thesis",
      "entry_logic": "Why this exact entry price — what level, why enter here",
      "exit_logic": "Why this exact target — what resistance/support, why 3-5%+ is realistic here",
      "probability_pct": 60,
      "probability_reasoning": "1-2 sentences on what drove this probability estimate up or down",
      "catalysts": ["catalyst1", "catalyst2"]
    }}
  ],
  "positions_to_close": ["TICKER1"],
  "portfolio_note": "Brief note on portfolio management reasoning for today",
  "risks": ["risk1","risk2","risk3"],
  "data_freshness": "note on data freshness"
}}
Picks: 1-5 stocks. REAL prices from web search. Mix long/short. Target MUST be ≥3% from entry. Total position_size_usd must not exceed ${current_capital:,.2f}."""

USER_PROMPT = f"Generate morning brief for {DATE_STR}. Search current data. Return only JSON."

print(f"🔍 Generuji morning brief pro {DATE_STR} | Kapitál: ${current_capital:,.2f}")

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4000,
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
