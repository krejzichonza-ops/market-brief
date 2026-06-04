# 📊 Market Morning Brief

Automatický AI-generovaný přehled amerického akciového trhu. Každý pracovní den GitHub Actions spustí analýzu, uloží výsledky a dashboard je zobrazí.

## Jak to funguje

```
09:15 ET → GitHub Actions → morning_brief.py → Anthropic API (web search) → data/YYYY-MM-DD.json
16:30 ET → GitHub Actions → evening_review.py → Anthropic API (web search) → data/YYYY-MM-DD.json (update)
```

Dashboard (`docs/index.html`) čte JSON soubory přímo z tohoto repozitáře přes GitHub raw URL.

## Setup (5 minut)

### 1. Fork nebo vytvoř repozitář
```bash
git clone https://github.com/tvoje-jmeno/market-brief.git
cd market-brief
```

### 2. Přidej Anthropic API klíč
`Settings → Secrets and variables → Actions → New repository secret`
- Name: `ANTHROPIC_API_KEY`
- Value: tvůj klíč z [console.anthropic.com](https://console.anthropic.com)

### 3. Povol GitHub Actions
`Actions → Enable Actions` (pokud je potřeba)

### 4. Povol GitHub Pages
`Settings → Pages → Source: Deploy from branch → Branch: main, /docs`

Dashboard bude dostupný na: `https://tvoje-jmeno.github.io/market-brief`

### 5. Nastav repozitář v dashboardu
Otevři dashboard → Setup záložka → zadej username a repo název → Save

## Soubory

```
.github/
  workflows/
    morning-brief.yml   ← GitHub Actions cron schedule
scripts/
  morning_brief.py      ← Generuje ranní analýzu (09:15 ET)
  evening_review.py     ← Generuje večerní review (16:30 ET)
docs/
  index.html            ← Dashboard (GitHub Pages)
data/
  YYYY-MM-DD.json       ← Generovaná data (auto)
```

## Timing

| Akce | UTC | ET (léto) | CZ (léto) |
|---|---|---|---|
| Morning Brief | 13:15 | 09:15 | 15:15 |
| Evening Review | 20:30 | 16:30 | 22:30 |

> ⚠️ GitHub Actions mohou mít zpoždění 5–15 minut v době vysokého zatížení.

## Manuální spuštění

`Actions → Market Morning Brief → Run workflow → vybrat mode (morning/evening)`

## Zimní čas (EST)

V zimě je ET = UTC-5. Uprav cron v `.github/workflows/morning-brief.yml`:
```yaml
- cron: '15 14 * * 1-5'   # 09:15 EST = 14:15 UTC
- cron: '30 21 * * 1-5'   # 16:30 EST = 21:30 UTC
```

## Disclaimer

AI-generované projekce jsou pouze pro vzdělávací účely. NEJSOU investičním doporučením.
