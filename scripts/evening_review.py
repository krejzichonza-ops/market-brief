#!/usr/bin/env python3
"""
Evening Review Generator — optimalizovaná verze
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

# Pokud dnešní brief neexistuje nebo je už zhodnocený, najdi nejnovější
# nezhodnocený brief (řeší případ kdy evening review proběhne se zpožděním
# přes půlnoc nebo víkend).
def find_target_file():
    if os.path.exists(INPUT_FILE):
        with open(INPUT_FILE) as f:
            rec = json.load(f)
        if rec.get('brief') and not rec.get('reviewed'):
            return INPUT_FILE, rec
    # Hledej nejnovější nezhodnocený brief mezi posledními 5 dny
    import glob
    candidates = sorted(glob.glob(os.path.join(DATA_DIR, '????-??-??.json')), reverse=True)
    for path in candidates[:5]:
        with open(path) as f:
            rec = json.load(f)
        if rec.get('brief') and not rec.get('reviewed'):
            return path, rec
    return None, None

INPUT_FILE, record = find_target_file()

if INPUT_FILE is None:
    print(f"⚠️  Žádný nezhodnocený morning brief nenalezen (kontrolováno do {DATE_KEY}).")
    sys.exit(0)

# Přepiš DATE_KEY/DATE_STR/DOW podle skutečně zpracovávaného briefu
brief_date_key = record['brief'].get('date_key', os.path.basename(INPUT_FILE).replace('.json', ''))
DATE_KEY = brief_date_key
DATE_STR = record['brief'].get('market_date', DATE_STR)
DOW = record['brief'].get('day_of_week', DOW)

print(f"📄 Zpracovávám brief: {INPUT_FILE} ({DATE_STR})")

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

SYSTEM_PROMPT = f"""Jsi profesionální portfolio manažer amerických akcií. Dnes je {DATE_STR} ({DOW}).

Piš VEŠKERÝ text v češtině. Ponech tickery, názvy společností a čísla v originále.

Vyhledej SKUTEČNÉ závěrečné ceny a intraday data (open/high/low/close) pro každý ticker.

VÝPOČET P&L:
- LONG: pnl_pct = (exit_price - entry_price) / entry_price * 100
- SHORT: pnl_pct = (entry_price - exit_price) / entry_price * 100
- Stop zasažen: použij stop_loss cenu. Target zasažen: použij target_price.
- Holding_days > 1 a stop/target nezasažen: outcome = held_open

MAE/MFE:
- MAE (Max Adverse Excursion): jak daleko šla cena PROTI pozici
  * LONG: (entry - session_low) / entry * 100
  * SHORT: (session_high - entry) / entry * 100
- MFE (Max Favorable Excursion): jak daleko šla cena VE PROSPĚCH
  * LONG: (session_high - entry) / entry * 100
  * SHORT: (entry - session_low) / entry * 100

POST-MORTEM THESIS: zhodnoť každou část původní teze.

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
      "commentary": "MAX 2 VĚTY co se stalo",
      "thesis_macro_verdict": "MAX 10 SLOV",
      "thesis_technical_verdict": "MAX 10 SLOV",
      "thesis_catalyst_verdict": "MAX 10 SLOV",
      "thesis_options_verdict": "MAX 10 SLOV",
      "thesis_volume_verdict": "MAX 10 SLOV",
      "thesis_miss_reason": "wrong_direction|catalyst_delayed|macro_reversal|stop_too_tight|target_too_aggressive|missed_entry|broader_market_drag|sector_specific_news|low_volume|options_misleading|other|n/a",
      "what_worked": "co z analýzy bylo správně",
      "what_failed": "co bylo špatně nebo n/a",
      "original_probability_pct": 0,
      "probability_verdict": "calibrated|overconfident|underconfident",
      "probability_comment": "1 věta o kvalitě odhadu pravděpodobnosti"
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
  "lessons": ["poučení1", "poučení2"],
  "tomorrow_watch": ["co sledovat zítra1", "co sledovat zítra2"]
}}"""

USER_PROMPT = f"""Zhodnoť dnešní picky ({DATE_STR}):
{picks_json}

Alokováno: ${total_allocated:,.2f}
Vyhledej skutečné intraday ceny. Vypočítej MAE, MFE a P&L. Vrať pouze JSON."""

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

# ── P&L VALIDACE — oprav nerealistické výsledky ───────────────────────────────
def validate_and_fix_pick(p, original_pick):
    """
    Zkontroluje P&L vůči stop lossu a take profitu z morning briefu.
    Pokud Claude vrátil nerealistické číslo, oprav ho na stop nebo target cenu.
    """
    ticker = p.get('ticker', '?')
    direction = p.get('direction', 'long')
    outcome = p.get('outcome', '')
    pos_size = float(p.get('position_size_usd') or original_pick.get('position_size_usd') or 0)

    entry = float(p.get('projected_entry') or original_pick.get('entry_price') or 0)
    target = float(p.get('projected_target') or original_pick.get('target_price') or 0)
    stop = float(p.get('projected_stop') or original_pick.get('stop_loss') or 0)
    exit_price = float(p.get('exit_price') or p.get('actual_close') or 0)

    if entry <= 0 or pos_size <= 0:
        return p  # nedostatek dat, neopravuj

    # Maximální povolená ztráta = stop loss distance + 1% buffer
    if direction == 'long':
        max_loss_pct = ((entry - stop) / entry * 100) + 1.0 if stop > 0 else 6.0
        max_gain_pct = ((target - entry) / entry * 100) + 1.0 if target > 0 else 15.0
    else:
        max_loss_pct = ((stop - entry) / entry * 100) + 1.0 if stop > 0 else 6.0
        max_gain_pct = ((entry - target) / entry * 100) + 1.0 if target > 0 else 15.0

    pnl_pct = float(p.get('pnl_pct') or 0)
    actual_loss = -pnl_pct if pnl_pct < 0 else 0
    actual_gain = pnl_pct if pnl_pct > 0 else 0

    corrected = False

    # Ztráta větší než stop loss → použij stop loss
    if actual_loss > max_loss_pct and stop > 0:
        print(f"⚠️  {ticker}: P&L {pnl_pct:.1f}% překračuje max ztrátu {-max_loss_pct:.1f}% → opravuji na stop loss")
        if direction == 'long':
            pnl_pct = (stop - entry) / entry * 100
        else:
            pnl_pct = (entry - stop) / entry * 100
        p['exit_price'] = stop
        p['outcome'] = 'stopped_out'
        corrected = True

    # Zisk větší než target → použij target cenu
    elif actual_gain > max_gain_pct and target > 0:
        print(f"⚠️  {ticker}: P&L {pnl_pct:.1f}% překračuje max zisk {max_gain_pct:.1f}% → opravuji na target")
        if direction == 'long':
            pnl_pct = (target - entry) / entry * 100
        else:
            pnl_pct = (entry - target) / entry * 100
        p['exit_price'] = target
        p['outcome'] = 'hit_target'
        corrected = True

    if corrected:
        pnl_usd = pos_size * (pnl_pct / 100)
        p['pnl_pct'] = round(pnl_pct, 2)
        p['pnl_usd'] = round(pnl_usd, 2)
        p['data_corrected'] = True
        print(f"   Opraveno: {pnl_pct:.2f}% = ${pnl_usd:.2f}")

    return p

# Aplikuj validaci na každý pick
pr_raw = review_data.get('picks_review', [])
picks_by_ticker = {p.get('ticker'): p for p in picks}
pr = [validate_and_fix_pick(p, picks_by_ticker.get(p.get('ticker'), {})) for p in pr_raw]
review_data['picks_review'] = pr

# ── Portfolio update ───────────────────────────────────────────────────────────
closed_today = [p for p in pr if p.get('outcome') != 'held_open']
held_open    = [p for p in pr if p.get('outcome') == 'held_open']

# Přepočítej portfolio summary z validovaných dat
real_pnl_usd = sum(float(p.get('pnl_usd') or 0) for p in closed_today)
# Unrealized z held_open (pouze informativní, nezahrnuj do kapitálu)
new_capital = round(portfolio['current_capital'] + real_pnl_usd, 2)

if new_capital <= 0 or new_capital > 10_000_000:
    new_capital = portfolio['current_capital']

# Aktualizuj portfolio_summary ve výstupu
ps = review_data.get('portfolio_summary', {})
ps['total_pnl_usd'] = round(real_pnl_usd, 2)
ps['new_capital_available'] = new_capital
review_data['portfolio_summary'] = ps

total_pnl_usd = real_pnl_usd

portfolio['current_capital'] = new_capital
portfolio['peak_capital'] = max(portfolio['peak_capital'], new_capital)

portfolio['total_trades']   += len(closed_today)
portfolio['winning_trades'] += sum(1 for p in closed_today if float(p.get('pnl_usd') or 0) > 0)
portfolio['losing_trades']  += sum(1 for p in closed_today if float(p.get('pnl_usd') or 0) <= 0)

portfolio['equity_curve'].append({
    "date": DATE_KEY,
    "day_of_week": DOW,
    "value": new_capital,
    "pnl_usd": round(real_pnl_usd, 2),
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

print(f"✅ Review uložen | Grade: {review_data.get('overall_grade')} | P&L: ${total_pnl_usd:+,.2f} | Portfolio: ${new_capital:,.2f}")
