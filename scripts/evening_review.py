#!/usr/bin/env python3
"""
Evening Review Generator — denní režim (všechny pozice se uzavírají na konci dne)
"""

import anthropic, json, os, re, sys, glob
from datetime import datetime
import pytz

ET = pytz.timezone('America/New_York')
now_et = datetime.now(ET)
DATE_KEY = now_et.strftime('%Y-%m-%d')
DATE_STR = now_et.strftime('%A, %B %d, %Y')
DOW = now_et.strftime('%A')
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
PORTFOLIO_FILE = os.path.join(DATA_DIR, 'portfolio.json')

def find_target_file():
    today_file = os.path.join(DATA_DIR, f'{DATE_KEY}.json')
    if os.path.exists(today_file):
        with open(today_file) as f:
            rec = json.load(f)
        if rec.get('brief') and not rec.get('reviewed'):
            return today_file, rec
    candidates = sorted(glob.glob(os.path.join(DATA_DIR, '????-??-??.json')), reverse=True)
    for path in candidates[:5]:
        with open(path) as f:
            rec = json.load(f)
        if rec.get('brief') and not rec.get('reviewed'):
            return path, rec
    return None, None

INPUT_FILE, record = find_target_file()

if INPUT_FILE is None:
    print(f"⚠️  Žádný nezhodnocený morning brief nenalezen.")
    sys.exit(0)

brief = record['brief']
picks = brief.get('picks', [])
picks_json = json.dumps(picks, ensure_ascii=False)

brief_date_key = record['brief'].get('date_key', os.path.basename(INPUT_FILE).replace('.json', ''))
DATE_KEY = brief_date_key
DATE_STR = record['brief'].get('market_date', DATE_STR)
DOW = record['brief'].get('day_of_week', DOW)

print(f"📄 Zpracovávám brief: {INPUT_FILE} ({DATE_STR})")

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
        "equity_curve": [],
        "open_positions": [],
        "closed_trades": []
    }

portfolio = load_portfolio()
total_allocated = sum(p.get('position_size_usd', 0) for p in picks)

client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])

SYSTEM_PROMPT = f"""Jsi profesionální intraday portfolio manažer amerických akcií. Dnes je {DATE_STR} ({DOW}).

Piš VEŠKERÝ text v češtině. Ponech tickery, názvy společností a čísla v originále.

DŮLEŽITÉ — DENNÍ REŽIM:
Všechny pozice se VŽDY uzavírají na konci obchodního dne (16:00 ET) za closing cenu.
- outcome = "hit_target" pokud intraday high (long) nebo low (short) dosáhl target price
- outcome = "stopped_out" pokud intraday low (long) nebo high (short) dosáhl stop loss
- outcome = "closed_eod" pokud ani target ani stop nebyl zasažen — pozice se uzavře za closing cenu
- outcome "held_open" a "missed_entry" NEEXISTUJÍ v denním režimu
- Vstup vždy proběhl za actual_open cenu (ne projected entry)

VÝPOČET P&L:
- LONG: pnl_pct = (exit_price - actual_open) / actual_open * 100
- SHORT: pnl_pct = (actual_open - exit_price) / actual_open * 100
- exit_price = target_price (hit_target) | stop_loss (stopped_out) | actual_close (closed_eod)
- Vstupní cena je vždy actual_open, ne projected entry

MAE/MFE:
- MAE: jak daleko šla cena PROTI pozici od actual_open
- MFE: jak daleko šla cena VE PROSPĚCH od actual_open

Vrať POUZE validní JSON:
{{
  "review_time": "ISO timestamp",
  "day_of_week": "{DOW}",
  "overall_grade": "A|B|C|D|F",
  "overall_score": 0-100,
  "index_recap": "S&P 500 a Nasdaq skutečné závěrečné hodnoty s % změnou",
  "narrative": "MAX 3 VĚTY — upřímné zhodnocení",
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
      "outcome": "hit_target|stopped_out|closed_eod",
      "pnl_pct": 0.0,
      "position_size_usd": 0.00,
      "pnl_usd": 0.00,
      "grade": "A|B|C|D|F",
      "mae_pct": 0.0,
      "mfe_pct": 0.0,
      "mae_vs_stop": "safe|close|triggered",
      "mfe_vs_target": "far|close|reached",
      "trade_quality": "excellent|good|scratchy|poor",
      "commentary": "MAX 2 VĚTY co se stalo intraday",
      "thesis_macro_verdict": "MAX 10 SLOV",
      "thesis_technical_verdict": "MAX 10 SLOV",
      "thesis_catalyst_verdict": "MAX 10 SLOV",
      "thesis_options_verdict": "MAX 10 SLOV",
      "thesis_volume_verdict": "MAX 10 SLOV",
      "thesis_miss_reason": "wrong_direction|catalyst_delayed|macro_reversal|stop_too_tight|target_too_aggressive|broader_market_drag|sector_specific_news|low_volume|other|n/a",
      "what_worked": "co z analýzy bylo správně",
      "what_failed": "co bylo špatně nebo n/a",
      "original_probability_pct": 0,
      "probability_verdict": "calibrated|overconfident|underconfident",
      "probability_comment": "MAX 1 VĚTA"
    }}
  ],
  "portfolio_summary": {{
    "capital_deployed": 0.00,
    "total_pnl_usd": 0.00,
    "total_pnl_pct": 0.0,
    "new_capital_available": 0.00
  }},
  "hit_rate": 0,
  "avg_pnl_pct": 0.0,
  "avg_mae_pct": 0.0,
  "avg_mfe_pct": 0.0,
  "lessons": ["poučení1", "poučení2"],
  "tomorrow_watch": ["co sledovat zítra1"]
}}"""

USER_PROMPT = f"""Zhodnoť dnešní intraday picky ({DATE_STR}):
{picks_json}

Alokováno: ${total_allocated:,.2f}
Vyhledej skutečné intraday ceny (open/high/low/close). Vstup byl za actual_open. Uzavření za closing cenu pokud nedosažen target/stop. Vrať pouze JSON."""

print(f"🔍 Evening review {DATE_STR} ({DOW}) | {len(picks)} pozic | Alokováno: ${total_allocated:,.2f}")

response = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=6000,
    system=SYSTEM_PROMPT,
    tools=[{"type": "web_search_20250305", "name": "web_search"}],
    messages=[{"role": "user", "content": USER_PROMPT}]
)

raw_text = ''.join(b.text for b in response.content if hasattr(b, 'text'))

def clean_text(text):
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    text = text.strip()
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return text

def extract_json(text):
    start = min(
        text.find('{') if '{' in text else len(text),
        text.find('[') if '[' in text else len(text)
    )
    json_str = text[start:]
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass
    last_brace = json_str.rfind('}')
    if last_brace > 0:
        try:
            return json.loads(json_str[:last_brace+1])
        except:
            pass
    return None

cleaned = clean_text(raw_text)
review_data = extract_json(cleaned)

if review_data is None:
    print(f"❌ JSON parse selhal")
    sys.exit(1)

# P&L validace
def validate_pick(p, original_pick):
    direction = p.get('direction', 'long')
    pos_size = float(p.get('position_size_usd') or original_pick.get('position_size_usd') or 0)
    entry = float(p.get('actual_open') or original_pick.get('entry_price') or 0)
    target = float(p.get('projected_target') or original_pick.get('target_price') or 0)
    stop = float(p.get('projected_stop') or original_pick.get('stop_loss') or 0)

    if entry <= 0 or pos_size <= 0:
        return p

    if direction == 'long':
        max_loss_pct = ((entry - stop) / entry * 100 + 1.0) if stop > 0 else 8.0
        max_gain_pct = ((target - entry) / entry * 100 + 1.0) if target > 0 else 15.0
    else:
        max_loss_pct = ((stop - entry) / entry * 100 + 1.0) if stop > 0 else 8.0
        max_gain_pct = ((entry - target) / entry * 100 + 1.0) if target > 0 else 15.0

    pnl_pct = float(p.get('pnl_pct') or 0)
    corrected = False

    if pnl_pct < 0 and abs(pnl_pct) > max_loss_pct and stop > 0:
        print(f"⚠️  {p.get('ticker')}: P&L {pnl_pct:.1f}% > max ztráta {-max_loss_pct:.1f}% → opravuji na stop")
        pnl_pct = (stop - entry) / entry * 100 if direction == 'long' else (entry - stop) / entry * 100
        p['exit_price'] = stop
        p['outcome'] = 'stopped_out'
        corrected = True
    elif pnl_pct > 0 and pnl_pct > max_gain_pct and target > 0:
        print(f"⚠️  {p.get('ticker')}: P&L {pnl_pct:.1f}% > max zisk {max_gain_pct:.1f}% → opravuji na target")
        pnl_pct = (target - entry) / entry * 100 if direction == 'long' else (entry - target) / entry * 100
        p['exit_price'] = target
        p['outcome'] = 'hit_target'
        corrected = True

    if corrected:
        p['pnl_pct'] = round(pnl_pct, 2)
        p['pnl_usd'] = round(pos_size * (pnl_pct / 100), 2)
        p['data_corrected'] = True

    return p

picks_by_ticker = {p.get('ticker'): p for p in picks}
pr = [validate_pick(p, picks_by_ticker.get(p.get('ticker'), {})) for p in review_data.get('picks_review', [])]
review_data['picks_review'] = pr

# Portfolio update — denní režim, žádné open_positions
real_pnl_usd = sum(float(p.get('pnl_usd') or 0) for p in pr)
new_capital = round(portfolio['current_capital'] + real_pnl_usd, 2)
if new_capital <= 0 or new_capital > 10_000_000:
    new_capital = portfolio['current_capital']

ps = review_data.get('portfolio_summary', {})
ps['total_pnl_usd'] = round(real_pnl_usd, 2)
ps['new_capital_available'] = new_capital
review_data['portfolio_summary'] = ps

portfolio['current_capital'] = new_capital
portfolio['peak_capital'] = max(portfolio['peak_capital'], new_capital)
portfolio['total_trades'] += len(pr)
portfolio['winning_trades'] += sum(1 for p in pr if float(p.get('pnl_usd') or 0) > 0)
portfolio['losing_trades'] += sum(1 for p in pr if float(p.get('pnl_usd') or 0) <= 0)

# Vždy prázdné open_positions v denním režimu
portfolio['open_positions'] = []

portfolio['equity_curve'].append({
    "date": DATE_KEY,
    "day_of_week": DOW,
    "value": new_capital,
    "pnl_usd": round(real_pnl_usd, 2),
    "grade": review_data.get('overall_grade', '?'),
    "avg_mae": review_data.get('avg_mae_pct', 0),
    "avg_mfe": review_data.get('avg_mfe_pct', 0)
})

for p in pr:
    portfolio['closed_trades'].append({
        "date": DATE_KEY,
        "day_of_week": DOW,
        "ticker": p['ticker'],
        "direction": p.get('direction', ''),
        "outcome": p.get('outcome', ''),
        "pnl_pct": p.get('pnl_pct', 0),
        "pnl_usd": p.get('pnl_usd', 0),
        "position_size_usd": p.get('position_size_usd', 0),
        "mae_pct": p.get('mae_pct', 0),
        "mfe_pct": p.get('mfe_pct', 0),
        "trade_quality": p.get('trade_quality', ''),
        "probability_pct": p.get('original_probability_pct', 0),
        "probability_verdict": p.get('probability_verdict', ''),
        "data_corrected": p.get('data_corrected', False)
    })

portfolio['closed_trades'] = portfolio['closed_trades'][-200:]

record['review'] = review_data
record['reviewed'] = True
record['reviewed_at'] = datetime.utcnow().isoformat()

with open(INPUT_FILE, 'w', encoding='utf-8') as f:
    json.dump(record, f, ensure_ascii=False, indent=2)

with open(PORTFOLIO_FILE, 'w', encoding='utf-8') as f:
    json.dump(portfolio, f, ensure_ascii=False, indent=2)

print(f"✅ Review uložen | Grade: {review_data.get('overall_grade')} | P&L: ${real_pnl_usd:+,.2f} | Portfolio: ${new_capital:,.2f}")
