#!/usr/bin/env python3
"""
Evening Review Generator v2 — s MAE/MFE tracking
16:30 ET každý pracovní den via GitHub Actions.
"""

import anthropic, json, os, re, sys
from datetime import datetime
import pytz

ET = pytz.timezone('America/New_York')
now_et = datetime.now(ET)
DATE_KEY = now_et.strftime('%Y-%m-%d')
DATE_STR = now_et.strftime('%A, %B %d, %Y')
DOW = now_et.strftime('%A')
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')

INPUT_FILE     = os.path.join(DATA_DIR, f'{DATE_KEY}.json')
PORTFOLIO_FILE = os.path.join(DATA_DIR, 'portfolio.json')

if not os.path.exists(INPUT_FILE):
    print(f"⚠️  Žádný morning brief pro {DATE_KEY}.")
    sys.exit(0)

with open(INPUT_FILE) as f:
    record = json.load(f)

if not record.get('brief'):
    print(f"⚠️  Morning brief prázdný.")
    sys.exit(0)

if record.get('reviewed'):
    print(f"✓ Evening review pro {DATE_KEY} již existuje.")
    sys.exit(0)

brief = record['brief']
picks = brief.get('picks', [])
picks_json = json.dumps(picks, ensure_ascii=False)

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
total_allocated = sum(p.get('position_size_usd', 0) for p in picks)

client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])

SYSTEM_PROMPT = f"""You are a professional US equity portfolio manager reviewing today's trades. Today is {DATE_STR} ({DOW}).

LANGUAGE: Write ALL text content in Czech language. Use proper Czech financial terminology. Only keep ticker symbols, company names, and numeric values in their original form.

Search for ACTUAL closing prices AND full intraday data (open, high, low, close, volume) for each ticker.

P&L RULES:
- LONG: pnl_pct = (exit_price - entry_price) / entry_price * 100
- SHORT: pnl_pct = (entry_price - exit_price) / entry_price * 100
- Stop hit: use stop_loss price. Target hit: use target_price. Neither: use actual_close.
- holding_days > 1 and no stop/target hit: outcome = "held_open"

MAE/MFE ANALYSIS — for every pick (critical for trade quality assessment):
- MAE (Maximum Adverse Excursion): How far did price move AGAINST the position before it resolved?
  * LONG: MAE = (entry_price - session_low) / entry_price * 100  [how close to stop did we get?]
  * SHORT: MAE = (session_high - entry_price) / entry_price * 100
- MFE (Maximum Favorable Excursion): How far did price move IN FAVOR of the position at its best point?
  * LONG: MFE = (session_high - entry_price) / entry_price * 100  [how close to target did we get?]
  * SHORT: MFE = (entry_price - session_low) / entry_price * 100
- mae_pct: the MAE value as positive number
- mfe_pct: the MFE value as positive number
- mae_vs_stop: "safe" (MAE < 50% of stop distance) | "close" (MAE 50-90% of stop) | "triggered" (stop was hit)
- mfe_vs_target: "far" (MFE < 50% of target distance) | "close" (MFE 50-90%) | "reached" (target was hit)
- trade_quality: Assessment based on MAE/MFE ratio:
  * "excellent": low MAE, high MFE — clean move in our direction
  * "good": moderate MAE, reached near target
  * "scratchy": high MAE but recovered
  * "poor": high MAE, low MFE — wrong from the start

THESIS POST-MORTEM:
- thesis_macro_verdict: Did macro thesis play out?
- thesis_technical_verdict: Did technical setup trigger? Where did price go vs expected level?
- thesis_catalyst_verdict: Did catalyst materialize?
- thesis_options_verdict: Did the options flow signal prove correct?
- thesis_volume_verdict: Did volume confirm or contradict the move?
- thesis_miss_reason: wrong_direction|catalyst_delayed|macro_reversal|stop_too_tight|target_too_aggressive|missed_entry|broader_market_drag|sector_specific_news|low_volume|options_misleading|other|n/a
- what_worked: What analysis was correct
- what_failed: What was wrong or missing

PROBABILITY CALIBRATION:
- original_probability_pct: copy exactly from morning pick
- probability_verdict: "calibrated"|"overconfident"|"underconfident"
- probability_comment: 1 honest sentence on calibration quality

Return ONLY valid JSON:
{{
  "review_time": "ISO timestamp",
  "day_of_week": "{DOW}",
  "overall_grade": "A|B|C|D|F",
  "overall_score": 0-100,
  "index_recap": "S&P 500 and Nasdaq actual closing numbers with % change",
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
      "actual_volume_vs_avg": "above|below|average",
      "exit_price": 0.00,
      "direction": "long|short",
      "holding_days": 1,
      "outcome": "hit_target|stopped_out|held_open|missed_entry",
      "pnl_pct": 0.0,
      "position_size_usd": 0.00,
      "pnl_usd": 0.00,
      "grade": "A|B|C|D|F",
      "mae_pct": 0.0,
      "mfe_pct": 0.0,
      "mae_vs_stop": "safe|close|triggered",
      "mfe_vs_target": "far|close|reached",
      "trade_quality": "excellent|good|scratchy|poor",
      "commentary": "2 sentences on what happened intraday",
      "thesis_macro_verdict": "...",
      "thesis_technical_verdict": "...",
      "thesis_catalyst_verdict": "...",
      "thesis_options_verdict": "Did options flow signal prove correct?",
      "thesis_volume_verdict": "Did volume confirm the move?",
      "thesis_miss_reason": "...|n/a",
      "what_worked": "...",
      "what_failed": "... or n/a",
      "original_probability_pct": 0,
      "probability_verdict": "calibrated|overconfident|underconfident",
      "probability_comment": "..."
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
  "avg_mae_pct": 0.0,
  "avg_mfe_pct": 0.0,
  "lessons": ["lesson1","lesson2"],
  "tomorrow_watch": ["item1","item2"]
}}"""

USER_PROMPT = f"""Review today's picks ({DATE_STR}):
{picks_json}

Total allocated: ${total_allocated:,.2f}
Search actual intraday prices (open/high/low/close/volume). Calculate MAE, MFE, P&L for each. Return only JSON."""

print(f"🔍 Evening review {DATE_STR} ({DOW}) | {len(picks)} pozic | Alokováno: ${total_allocated:,.2f}")

response = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=8000,
    system=SYSTEM_PROMPT,
    tools=[{"type": "web_search_20250305", "name": "web_search"}],
    messages=[{"role": "user", "content": USER_PROMPT}]
)

raw_text = ''.join(b.text for b in response.content if hasattr(b, 'text'))

def extract_json(text):
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    text = text.strip()
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    start = min(
        text.find('{') if '{' in text else len(text),
        text.find('[') if '[' in text else len(text)
    )
    json_str = text[start:]
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        last_brace = json_str.rfind('}')
        if last_brace > 0:
            try:
                return json.loads(json_str[:last_brace+1])
            except:
                pass
        raise

try:
    review_data = extract_json(raw_text)
except json.JSONDecodeError as e:
    print(f"❌ Parse error: {e}\n{raw_text[:300]}")
    sys.exit(1)

# ── Portfolio update ───────────────────────────────────────────────────────────
ps = review_data.get('portfolio_summary', {})
total_pnl_usd = ps.get('total_pnl_usd', 0.0)
new_capital = ps.get('new_capital_available', portfolio['current_capital'])

if new_capital <= 0 or new_capital > 10_000_000:
    new_capital = portfolio['current_capital'] + total_pnl_usd

portfolio['current_capital'] = round(new_capital, 2)
portfolio['peak_capital'] = max(portfolio['peak_capital'], new_capital)

pr = review_data.get('picks_review', [])
closed_today = [p for p in pr if p.get('outcome') != 'held_open']
held_open    = [p for p in pr if p.get('outcome') == 'held_open']

portfolio['total_trades']   += len(closed_today)
portfolio['winning_trades'] += sum(1 for p in closed_today if p.get('pnl_usd', 0) > 0)
portfolio['losing_trades']  += sum(1 for p in closed_today if p.get('pnl_usd', 0) <= 0)

portfolio['equity_curve'].append({
    "date": DATE_KEY,
    "day_of_week": DOW,
    "value": round(new_capital, 2),
    "pnl_usd": round(total_pnl_usd, 2),
    "grade": review_data.get('overall_grade', '?'),
    "avg_mae": review_data.get('avg_mae_pct', 0),
    "avg_mfe": review_data.get('avg_mfe_pct', 0)
})

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

for p in closed_today:
    portfolio['closed_trades'].append({
        "date": DATE_KEY,
        "day_of_week": DOW,
        "ticker": p['ticker'],
        "direction": p['direction'],
        "outcome": p['outcome'],
        "pnl_pct": p.get('pnl_pct', 0),
        "pnl_usd": p.get('pnl_usd', 0),
        "position_size_usd": p.get('position_size_usd', 0),
        "mae_pct": p.get('mae_pct', 0),
        "mfe_pct": p.get('mfe_pct', 0),
        "trade_quality": p.get('trade_quality', ''),
        "probability_pct": p.get('original_probability_pct', 0),
        "probability_verdict": p.get('probability_verdict', '')
    })

portfolio['closed_trades'] = portfolio['closed_trades'][-200:]

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
