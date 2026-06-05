#!/usr/bin/env python3
"""
Evening Review Generator — s portfolio vyhodnocením
16:30 ET každý pracovní den via GitHub Actions.
"""

import anthropic, json, os, re, sys
from datetime import datetime
import pytz

ET = pytz.timezone('America/New_York')
now_et = datetime.now(ET)
DATE_KEY = now_et.strftime('%Y-%m-%d')
DATE_STR = now_et.strftime('%A, %B %d, %Y')
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')

INPUT_FILE  = os.path.join(DATA_DIR, f'{DATE_KEY}.json')
PORTFOLIO_FILE = os.path.join(DATA_DIR, 'portfolio.json')

# ── Kontroly ───────────────────────────────────────────────────────────────────
if not os.path.exists(INPUT_FILE):
    print(f"⚠️  Žádný morning brief pro {DATE_KEY}.")
    sys.exit(0)

with open(INPUT_FILE) as f:
    record = json.load(f)

if not record.get('brief'):
    print(f"⚠️  Morning brief pro {DATE_KEY} je prázdný.")
    sys.exit(0)

if record.get('reviewed'):
    print(f"✓ Evening review pro {DATE_KEY} již existuje.")
    sys.exit(0)

brief = record['brief']
picks = brief.get('picks', [])
picks_json = json.dumps(picks, ensure_ascii=False)

# ── Portfolio stav ─────────────────────────────────────────────────────────────
def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE) as f:
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

# Spočítej celkový nasazený kapitál z dnešních picků
total_allocated = sum(p.get('position_size_usd', 0) for p in picks)

client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])

SYSTEM_PROMPT = f"""You are a professional US equity portfolio manager reviewing today's trades. Today is {DATE_STR}.

Search for ACTUAL closing prices (and intraday high/low) for each ticker. Evaluate each position honestly.

For each pick, determine:
- Was the stop loss HIT during the session? (check intraday low for longs, high for shorts)
- Was the take profit HIT during the session?
- If neither: position closes at end-of-day price (unless holding_days > 1, then it remains open)

P&L calculation:
- LONG: pnl_pct = (exit_price - entry_price) / entry_price * 100
- SHORT: pnl_pct = (entry_price - exit_price) / entry_price * 100
- If stopped out: use stop_loss price. If target hit: use target_price.

THESIS POST-MORTEM — for every pick you MUST evaluate the original thesis:
- thesis_macro_verdict: Did the macro thesis play out? What actually happened in the macro environment?
- thesis_technical_verdict: Did the technical setup trigger as expected? Where did price actually go vs the expected level?
- thesis_catalyst_verdict: Did the catalyst materialize? If not, what happened instead?
- thesis_miss_reason: If the trade failed or underperformed, what was the PRIMARY reason? Choose one: wrong_direction | catalyst_delayed | macro_reversal | stop_too_tight | target_too_aggressive | missed_entry | broader_market_drag | sector_specific_news | other
- what_worked: What part of the original analysis was correct?
- what_failed: What part was wrong or missing?

PROBABILITY CALIBRATION — for every pick:
- original_probability_pct: copy the probability_pct exactly as stated in the morning pick
- probability_verdict: evaluate the calibration quality:
  * "calibrated" — the stated probability matched the outcome reasonably (e.g. 65% and it hit target, or 40% and it failed)
  * "overconfident" — stated high probability (>60%) but trade failed / was stopped out
  * "underconfident" — stated low probability (<50%) but trade hit target cleanly
- probability_comment: 1 honest sentence assessing whether the confidence level was appropriate given what actually happened

Return ONLY valid JSON:
{{
  "review_time": "ISO timestamp",
  "overall_grade": "A|B|C|D|F",
  "overall_score": 0-100,
  "index_recap": "S&P 500 and Nasdaq actual closing numbers today",
  "narrative": "2-3 paragraph honest assessment",
  "picks_review": [
    {{
      "ticker": "AAPL",
      "projected_entry": 0.00,
      "projected_target": 0.00,
      "projected_stop": 0.00,
      "actual_open": 0.00,
      "actual_high": 0.00,
      "actual_low": 0.00,
      "actual_close": 0.00,
      "exit_price": 0.00,
      "direction": "long|short",
      "holding_days": 1,
      "outcome": "hit_target|stopped_out|held_open|missed_entry",
      "pnl_pct": 0.0,
      "position_size_usd": 0.00,
      "pnl_usd": 0.00,
      "grade": "A|B|C|D|F",
      "commentary": "2 sentences on what happened intraday",
      "thesis_macro_verdict": "Did macro thesis play out? What actually happened?",
      "thesis_technical_verdict": "Did the technical setup trigger? Where did price go vs expected?",
      "thesis_catalyst_verdict": "Did the catalyst materialize? What happened instead if not?",
      "thesis_miss_reason": "wrong_direction|catalyst_delayed|macro_reversal|stop_too_tight|target_too_aggressive|missed_entry|broader_market_drag|sector_specific_news|other|n/a",
      "what_worked": "What part of the original analysis was correct",
      "what_failed": "What part was wrong or missing (or 'n/a' if trade succeeded)",
      "original_probability_pct": 0,
      "probability_verdict": "calibrated|overconfident|underconfident",
      "probability_comment": "1 sentence: was the confidence level appropriate given what actually happened?"
    }}
  ],
  "portfolio_summary": {{
    "capital_deployed": 0.00,
    "total_pnl_usd": 0.00,
    "total_pnl_pct": 0.0,
    "positions_closed_today": ["TICKER1"],
    "positions_held_open": ["TICKER2"],
    "new_capital_available": 0.00
  }},
  "hit_rate": 0-100,
  "avg_pnl_pct": 0.0,
  "lessons": ["lesson1","lesson2"],
  "tomorrow_watch": ["item1","item2"]
}}

For positions with holding_days > 1 that didn't hit stop or target: outcome = "held_open", use actual_close for unrealized pnl, they stay in portfolio."""

USER_PROMPT = f"""Review today's picks ({DATE_STR}):
{picks_json}

Total allocated: ${total_allocated:,.2f}
Search actual prices. Calculate P&L in USD per position. Return only JSON."""

print(f"🔍 Evening review {DATE_STR} | {len(picks)} pozic | Alokováno: ${total_allocated:,.2f}")

response = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=3500,
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
    review_data = extract_json(raw_text)
except json.JSONDecodeError as e:
    print(f"❌ Parse error: {e}\n{raw_text[:300]}")
    sys.exit(1)

# ── Aktualizace portfolia ──────────────────────────────────────────────────────
ps = review_data.get('portfolio_summary', {})
total_pnl_usd = ps.get('total_pnl_usd', 0.0)
new_capital = ps.get('new_capital_available', portfolio['current_capital'])

# Zajisti rozumné číslo
if new_capital <= 0 or new_capital > 10_000_000:
    new_capital = portfolio['current_capital'] + total_pnl_usd

portfolio['current_capital'] = round(new_capital, 2)
portfolio['peak_capital'] = max(portfolio['peak_capital'], new_capital)

# Statistiky obchodů
pr = review_data.get('picks_review', [])
closed_today = [p for p in pr if p.get('outcome') != 'held_open']
held_open = [p for p in pr if p.get('outcome') == 'held_open']

portfolio['total_trades'] += len(closed_today)
portfolio['winning_trades'] += sum(1 for p in closed_today if p.get('pnl_usd', 0) > 0)
portfolio['losing_trades']  += sum(1 for p in closed_today if p.get('pnl_usd', 0) <= 0)

# Equity curve bod
portfolio['equity_curve'].append({
    "date": DATE_KEY,
    "value": round(new_capital, 2),
    "pnl_usd": round(total_pnl_usd, 2),
    "grade": review_data.get('overall_grade', '?')
})

# Open positions pro zítra
portfolio['open_positions'] = []
for p in held_open:
    original = next((x for x in picks if x['ticker'] == p['ticker']), {})
    portfolio['open_positions'].append({
        "ticker": p['ticker'],
        "company": original.get('company', ''),
        "direction": p['direction'],
        "entry_price": p['projected_entry'],
        "target_price": p['projected_target'],
        "stop_loss": p['projected_stop'],
        "position_size_usd": p.get('position_size_usd', 0),
        "holding_days_remaining": max(1, original.get('holding_days', 1) - 1),
        "unrealized_pnl_pct": p.get('pnl_pct', 0),
        "opened_date": DATE_KEY
    })

# Closed trades log
for p in closed_today:
    portfolio['closed_trades'].append({
        "date": DATE_KEY,
        "ticker": p['ticker'],
        "direction": p['direction'],
        "outcome": p['outcome'],
        "pnl_pct": p.get('pnl_pct', 0),
        "pnl_usd": p.get('pnl_usd', 0),
        "position_size_usd": p.get('position_size_usd', 0)
    })

# Zachovej jen posledních 200 uzavřených obchodů
portfolio['closed_trades'] = portfolio['closed_trades'][-200:]

# ── Uložení ────────────────────────────────────────────────────────────────────
record['review'] = review_data
record['reviewed'] = True
record['reviewed_at'] = datetime.utcnow().isoformat()

with open(INPUT_FILE, 'w', encoding='utf-8') as f:
    json.dump(record, f, ensure_ascii=False, indent=2)

with open(PORTFOLIO_FILE, 'w', encoding='utf-8') as f:
    json.dump(portfolio, f, ensure_ascii=False, indent=2)

max_dd = 0
if len(portfolio['equity_curve']) > 1:
    peak = portfolio['starting_capital']
    for pt in portfolio['equity_curve']:
        peak = max(peak, pt['value'])
        dd = (peak - pt['value']) / peak * 100
        max_dd = max(max_dd, dd)

print(f"✅ Review uložen | Grade: {review_data.get('overall_grade')} | P&L: ${total_pnl_usd:+,.2f} | Portfolio: ${new_capital:,.2f} | Max DD: {max_dd:.1f}%")
