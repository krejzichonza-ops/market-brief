#!/usr/bin/env python3
"""
Zpetny prepocet P&L pro vsechny historicke JSON soubory.
Opravuje SHORT pozice kde bylo spatne znamenko.
"""

import json, os, glob

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')

def recalculate_pick(p):
    direction = p.get('direction', 'long')
    pos_size = float(p.get('position_size_usd') or 0)
    entry = float(p.get('actual_open') or p.get('projected_entry') or 0)
    exit_price = float(p.get('exit_price') or p.get('actual_close') or 0)

    if entry <= 0 or exit_price <= 0 or pos_size <= 0:
        return p, False

    if direction == 'long':
        correct_pnl_pct = (exit_price - entry) / entry * 100
    else:
        correct_pnl_pct = (entry - exit_price) / entry * 100

    correct_pnl_usd = pos_size * (correct_pnl_pct / 100)
    old_pnl_pct = float(p.get('pnl_pct') or 0)

    changed = abs(correct_pnl_pct - old_pnl_pct) > 0.05

    if changed:
        p['pnl_pct'] = round(correct_pnl_pct, 2)
        p['pnl_usd'] = round(correct_pnl_usd, 2)
        p['data_corrected'] = True

    return p, changed

files = sorted(glob.glob(os.path.join(DATA_DIR, '????-??-??.json')))
print(f"Nalezeno {len(files)} souboru")

total_changes = 0
daily_pnl = {}

for filepath in files:
    date_key = os.path.basename(filepath).replace('.json', '')
    with open(filepath, encoding='utf-8') as f:
        record = json.load(f)

    review = record.get('review')
    if not review:
        continue

    picks_review = review.get('picks_review', [])
    file_changed = False
    day_pnl = 0.0

    for i, p in enumerate(picks_review):
        old_pnl = float(p.get('pnl_usd') or 0)
        p, changed = recalculate_pick(p)
        picks_review[i] = p
        day_pnl += float(p.get('pnl_usd') or 0)
        if changed:
            print(f"  {date_key} | {p['ticker']} ({p.get('direction','?').upper()}): {old_pnl:+.2f} -> {p['pnl_usd']:+.2f}")
            file_changed = True
            total_changes += 1

    if file_changed:
        ps = review.get('portfolio_summary', {})
        ps['total_pnl_usd'] = round(day_pnl, 2)
        review['portfolio_summary'] = ps
        record['review'] = review
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(record, f, ensure_ascii=False, indent=2)

    daily_pnl[date_key] = day_pnl

# Prepocitej portfolio.json
portfolio_file = os.path.join(DATA_DIR, 'portfolio.json')
if os.path.exists(portfolio_file):
    with open(portfolio_file, encoding='utf-8') as f:
        portfolio = json.load(f)

    current = float(portfolio.get('starting_capital', 100000.0))
    peak = current

    for pt in portfolio.get('equity_curve', []):
        date = pt.get('date', '')
        if date in daily_pnl:
            pnl = daily_pnl[date]
            current = round(current + pnl, 2)
            peak = max(peak, current)
            pt['value'] = current
            pt['pnl_usd'] = round(pnl, 2)

    portfolio['current_capital'] = current
    portfolio['peak_capital'] = peak

    closed = portfolio.get('closed_trades', [])
    portfolio['winning_trades'] = sum(1 for t in closed if float(t.get('pnl_usd', 0)) > 0)
    portfolio['losing_trades'] = sum(1 for t in closed if float(t.get('pnl_usd', 0)) <= 0)

    with open(portfolio_file, 'w', encoding='utf-8') as f:
        json.dump(portfolio, f, ensure_ascii=False, indent=2)

    print(f"\nPortfolio prepocitano | Kapital: ${current:,.2f}")

print(f"\nCelkem opraveno {total_changes} P&L hodnot")
