#!/usr/bin/env python3
"""
Morning Brief Generator — optimalizovaná verze
09:15 ET každý pracovní den via GitHub Actions.
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
        print(f"✓ Morning brief pro {DATE_KEY} již existuje.")
        sys.exit(0)

open_pos_str = "žádné" if not open_positions else json.dumps(open_positions, ensure_ascii=False)

client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])

SYSTEM_PROMPT = f"""Jsi profesionální portfolio manažer amerických akcií s přístupem k web search. Dnes je {DATE_STR} ({DOW}).

Piš VEŠKERÝ text v češtině. Ponech tickery, názvy společností a čísla v originále.

STAV PORTFOLIA:
- Disponibilní kapitál: ${current_capital:,.2f}
- Otevřené pozice: {open_pos_str}

ÚKOL — vyhledej a analyzuj:
1. US futures (S&P 500, Nasdaq, Dow), VIX, 10Y výnos, DXY, ropa, zlato
2. Klíčové pre-market pohyby a jejich důvody
3. Makro události dnes a tento týden (Fed, CPI, NFP, PMI)
4. Geopolitické faktory ovlivňující trhy
5. Earnings tento týden — které firmy reportují?
6. Put/call ratio S&P 500 a neobvyklý options flow
7. Krátkodobý zájem (short interest) u potenciálních picků
8. Insider trading — SEC Form 4 za posledních 48h

VÝBĚR PICKŮ (1-5 pozic):
- Diverzifikuj — nevybírej 2 akcie ze stejného sub-sektoru
- Target minimálně 3% od entry (ideálně 5%+)
- Stop loss na technické úrovni, ne těsnější než 1%
- Holding 1-3 dny
- Celková alokace max ${current_capital:,.2f}

Vrať POUZE validní JSON bez markdown:
{{
  "generated_at": "ISO timestamp",
  "market_date": "{DATE_STR}",
  "date_key": "{DATE_KEY}",
  "day_of_week": "{DOW}",
  "snapshot": {{
    "sp500_futures": "hodnota+%",
    "nasdaq_futures": "hodnota+%",
    "dow_futures": "hodnota+%",
    "vix": "hodnota",
    "us10y": "výnos%",
    "dxy": "hodnota",
    "crude_oil": "cena",
    "gold": "cena"
  }},
  "market_context": {{
    "vix_regime": "low|normal|elevated|high",
    "options_pcr": "hodnota nebo unavailable",
    "market_volume": "above_average|average|below_average",
    "earnings_this_week": ["TICKER: datum"],
    "insider_activity_summary": "shrnutí insider aktivity"
  }},
  "overall_sentiment": "bullish|neutral|bearish",
  "sentiment_score": 0-100,
  "key_themes": ["téma1", "téma2", "téma3"],
  "macro_summary": "2 odstavce o makro situaci",
  "afterhours_summary": "1-2 odstavce o pre-market pohybech",
  "geopolitical_summary": "1 odstavec o geopolitice",
  "sectors": [
    {{"name": "Technology", "signal": "bullish|neutral|bearish", "score": 0-100, "reason": "důvod"}},
    {{"name": "Financials", "signal": "bullish|neutral|bearish", "score": 0-100, "reason": ""}},
    {{"name": "Energy", "signal": "bullish|neutral|bearish", "score": 0-100, "reason": ""}},
    {{"name": "Healthcare", "signal": "bullish|neutral|bearish", "score": 0-100, "reason": ""}},
    {{"name": "Industrials", "signal": "bullish|neutral|bearish", "score": 0-100, "reason": ""}}
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
      "thesis_macro": "makro kontext pro tento trade",
      "thesis_technical": "technický setup — pattern, klíčové úrovně",
      "thesis_catalyst": "konkrétní katalyzátor pohybu",
      "thesis_options": "put/call ratio a neobvyklý options flow",
      "thesis_short_interest": "short interest % float",
      "thesis_insider": "insider filingy nebo Žádné nedávné insider filingy",
      "thesis_volume": "objem vs 20denní průměr",
      "thesis_correlation": "proč není korelovaný s ostatními picky",
      "thesis_risk": "hlavní riziko invalidující tezi",
      "entry_logic": "proč právě tato vstupní cena",
      "exit_logic": "proč je target realistický",
      "probability_pct": 60,
      "probability_reasoning": "co ovlivnilo odhad pravděpodobnosti",
      "catalysts": ["katalyzátor1"]
    }}
  ],
  "portfolio_note": "poznámka k řízení portfolia",
  "risks": ["riziko1", "riziko2", "riziko3"],
  "data_freshness": "poznámka o aktuálnosti dat"
}}"""

USER_PROMPT = f"Vygeneruj morning brief pro {DATE_STR}. Vyhledej aktuální data. Vrať pouze JSON."

print(f"🔍 Generuji morning brief pro {DATE_STR} ({DOW}) | Kapitál: ${current_capital:,.2f}")

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
    # Pass 1: try full text
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass
    # Pass 2: find last valid closing brace
    last_brace = json_str.rfind('}')
    if last_brace > 0:
        try:
            return json.loads(json_str[:last_brace+1])
        except:
            pass
    # Pass 3: ask Claude to fix the JSON
    return None

cleaned = clean_text(raw_text)
brief_data = extract_json(cleaned)

if brief_data is None:
    print("⚠️  JSON parse selhal, žádám o opravu...")
    fix_response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=6000,
        messages=[{
            "role": "user",
            "content": f"Následující text obsahuje neúplný nebo poškozený JSON. Oprav ho a vrať POUZE validní JSON bez jakéhokoliv dalšího textu:\n\n{cleaned[:8000]}"
        }]
    )
    fixed_text = clean_text(''.join(b.text for b in fix_response.content if hasattr(b, 'text')))
    brief_data = extract_json(fixed_text)
    if brief_data is None:
        print(f"❌ JSON nelze opravit")
        sys.exit(1)
    print("✅ JSON opraven")

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
