#!/usr/bin/env python3
"""
Email notifikace po každém morning briefu a evening review.
Posílá přehledný HTML email s klíčovými daty.
"""

import json
import os
import smtplib
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import pytz

# ── Konfigurace ────────────────────────────────────────────────────────────────
ET = pytz.timezone('America/New_York')
now_et = datetime.now(ET)
DATE_KEY = now_et.strftime('%Y-%m-%d')
DATE_STR = now_et.strftime('%A, %B %d, %Y')

GMAIL_ADDRESS     = os.environ.get('GMAIL_ADDRESS', '')
GMAIL_APP_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD', '')
RUN_MODE          = os.environ.get('RUN_MODE', 'morning')

DATA_DIR  = os.path.join(os.path.dirname(__file__), '..', 'data')
DATA_FILE = os.path.join(DATA_DIR, f'{DATE_KEY}.json')
DASHBOARD_URL = f"https://{GMAIL_ADDRESS.split('@')[0].replace('.','-')}.github.io/market-brief"

if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
    print("⚠️  GMAIL_ADDRESS nebo GMAIL_APP_PASSWORD není nastaven, přeskakuji email.")
    sys.exit(0)

if not os.path.exists(DATA_FILE):
    print(f"⚠️  Data soubor {DATA_FILE} nenalezen, přeskakuji email.")
    sys.exit(0)

with open(DATA_FILE, 'r') as f:
    record = json.load(f)

brief  = record.get('brief', {})
review = record.get('review', {})

# ── Helpers ────────────────────────────────────────────────────────────────────
def fmt_usd(n):
    try:
        return f"${float(n):,.2f}"
    except:
        return str(n)

def sentiment_color(s):
    return {'bullish': '#00d4aa', 'bearish': '#ff4060'}.get(s, '#ffb300')

def outcome_color(o):
    return {'hit_target': '#00d4aa', 'stopped_out': '#ff4060',
            'held_open': '#4da6ff', 'missed_entry': '#4a5a6a'}.get(o, '#4a5a6a')

def outcome_label(o):
    return {'hit_target': '✓ TARGET HIT', 'stopped_out': '✗ STOPPED OUT',
            'held_open': '→ HELD OPEN', 'missed_entry': '— MISSED ENTRY'}.get(o, o)

def prob_color(p):
    try:
        p = float(p)
        return '#00d4aa' if p >= 65 else '#ffb300' if p >= 50 else '#ff4060'
    except:
        return '#4a5a6a'

# ── CSS ────────────────────────────────────────────────────────────────────────
CSS = """
body { margin:0; padding:0; background:#07090c; font-family:'IBM Plex Sans',Arial,sans-serif; }
.wrap { max-width:640px; margin:0 auto; padding:24px 16px; }
.header { border-bottom:1px solid #1c2530; padding-bottom:16px; margin-bottom:20px; }
.logo { font-family:monospace; font-size:11px; color:#00d4aa; letter-spacing:.15em; text-transform:uppercase; margin-bottom:4px; }
.title { font-family:monospace; font-size:22px; font-weight:700; color:#deeaf6; }
.date  { font-family:monospace; font-size:11px; color:#4a5a6a; margin-top:4px; }
.card  { background:#0f1318; border:1px solid #1c2530; margin-bottom:16px; }
.card-hdr { padding:10px 14px; border-bottom:1px solid #1c2530; background:rgba(255,255,255,.015); }
.card-lbl { font-family:monospace; font-size:10px; font-weight:700; letter-spacing:.15em; text-transform:uppercase; color:#00d4aa; }
.card-body { padding:14px; }
.snap-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:1px; background:#1c2530; }
.snap-cell { background:#0f1318; padding:10px 12px; }
.snap-lbl  { font-family:monospace; font-size:9px; color:#4a5a6a; text-transform:uppercase; letter-spacing:.1em; margin-bottom:3px; }
.snap-val  { font-family:monospace; font-size:13px; font-weight:700; }
.pick { border:1px solid #1c2530; margin-bottom:10px; }
.pick-hdr { display:flex; align-items:center; justify-content:space-between; padding:10px 12px; border-bottom:1px solid #1c2530; background:rgba(255,255,255,.02); }
.pick-ticker { font-family:monospace; font-size:14px; font-weight:700; color:#deeaf6; }
.pick-co { font-size:10px; color:#4a5a6a; margin-top:2px; }
.pick-body { padding:10px 12px; font-size:12px; color:#b8c8d8; line-height:1.6; }
.prob-bar-wrap { height:4px; background:#1c2530; margin:6px 0; }
.prob-bar-fill { height:100%; }
.badge { display:inline-block; padding:2px 7px; font-family:monospace; font-size:9px; font-weight:700; border:1px solid; }
.tbl { width:100%; border-collapse:collapse; }
.tbl th { font-family:monospace; font-size:9px; color:#4a5a6a; text-transform:uppercase; padding:7px 10px; border-bottom:1px solid #1c2530; text-align:left; }
.tbl td { font-family:monospace; font-size:11px; padding:8px 10px; border-bottom:1px solid #1c2530; color:#b8c8d8; }
.tbl tr:last-child td { border:none; }
.prose { font-size:13px; color:#b8c8d8; line-height:1.7; }
.prose p { margin:0 0 8px 0; }
.btn { display:inline-block; padding:12px 28px; background:#00d4aa; color:#07090c; font-family:monospace; font-size:12px; font-weight:700; text-decoration:none; letter-spacing:.08em; text-transform:uppercase; }
.footer { padding:16px 0; font-family:monospace; font-size:9px; color:#4a5a6a; line-height:1.8; border-top:1px solid #1c2530; margin-top:24px; }
"""

# ── MORNING EMAIL ──────────────────────────────────────────────────────────────
def build_morning_html():
    snap = brief.get('snapshot', {})
    picks = brief.get('picks', [])
    sentiment = brief.get('overall_sentiment', 'neutral')
    sc = sentiment_color(sentiment)
    sent_label = {'bullish': '▲ BULLISH', 'bearish': '▼ BEARISH'}.get(sentiment, '◆ NEUTRAL')
    themes = brief.get('key_themes', [])
    risks = brief.get('risks', [])

    def snap_cell(label, val, color='#deeaf6'):
        return f"""<div class="snap-cell">
            <div class="snap-lbl">{label}</div>
            <div class="snap-val" style="color:{color}">{val or '—'}</div>
        </div>"""

    snap_html = f"""
        {snap_cell('S&P Fut', snap.get('sp500_futures'), '#ff4060' if snap.get('sp500_futures','').startswith('-') else '#00d4aa')}
        {snap_cell('NQ Fut',  snap.get('nasdaq_futures'), '#ff4060' if snap.get('nasdaq_futures','').startswith('-') else '#00d4aa')}
        {snap_cell('VIX',     snap.get('vix'))}
        {snap_cell('10Y UST', snap.get('us10y'))}
        {snap_cell('DXY',     snap.get('dxy'))}
        {snap_cell('Oil',     snap.get('crude_oil'))}
        {snap_cell('Gold',    snap.get('gold'))}
        {snap_cell('Dow Fut', snap.get('dow_futures'))}
    """

    picks_html = ''
    for i, p in enumerate(picks):
        direction = p.get('direction', 'long')
        dir_color = '#00d4aa' if direction == 'long' else '#ff4060'
        dir_label = '▲ LONG' if direction == 'long' else '▼ SHORT'
        prob = p.get('probability_pct')
        prob_html = ''
        if prob is not None:
            pc = prob_color(prob)
            prob_html = f"""
                <div style="margin-top:8px">
                    <div style="font-family:monospace;font-size:9px;color:#4a5a6a;margin-bottom:4px">🎲 PRAVDĚPODOBNOST TARGETU</div>
                    <div style="display:flex;align-items:center;gap:8px">
                        <div class="prob-bar-wrap" style="flex:1">
                            <div class="prob-bar-fill" style="width:{prob}%;background:{pc}"></div>
                        </div>
                        <span style="font-family:monospace;font-size:14px;font-weight:700;color:{pc}">{prob}%</span>
                    </div>
                    <div style="font-size:11px;color:#4a5a6a;margin-top:4px">{p.get('probability_reasoning','')}</div>
                </div>"""

        conf = p.get('confidence', '')
        conf_color = '#00d4aa' if conf == 'high' else '#ff4060' if conf == 'low' else '#ffb300'

        picks_html += f"""
        <div class="pick">
            <div class="pick-hdr">
                <div>
                    <div class="pick-ticker">{p.get('ticker','')}
                        <span style="font-size:11px;font-weight:400;color:#4a5a6a;margin-left:8px">{p.get('company','')}</span>
                    </div>
                </div>
                <div style="display:flex;align-items:center;gap:8px">
                    <span class="badge" style="color:{dir_color};border-color:{dir_color}">{dir_label}</span>
                    <span class="badge" style="color:{conf_color};border-color:{conf_color}">{conf.upper()}</span>
                    <span style="font-family:monospace;font-size:10px;color:#ffb300">{p.get('holding_days',1)}d</span>
                </div>
            </div>
            <div class="pick-body">
                <table style="width:100%;font-family:monospace;font-size:11px;margin-bottom:10px">
                    <tr>
                        <td style="color:#4a5a6a;padding:2px 0">Entry</td>
                        <td style="color:#00d4aa;font-weight:700">{fmt_usd(p.get('entry_price',0))}</td>
                        <td style="color:#4a5a6a;padding:2px 12px">Target</td>
                        <td style="color:#4da6ff;font-weight:700">{fmt_usd(p.get('target_price',0))}
                            <span style="color:#00d4aa;font-size:9px"> +{float(p.get('target_pct',0)):.1f}%</span></td>
                        <td style="color:#4a5a6a;padding:2px 12px">Stop</td>
                        <td style="color:#ff4060;font-weight:700">{fmt_usd(p.get('stop_loss',0))}
                            <span style="color:#ff4060;font-size:9px"> -{abs(float(p.get('stop_pct',0))):.1f}%</span></td>
                        <td style="color:#4a5a6a;padding:2px 12px">R/R</td>
                        <td style="color:#ffb300">{p.get('risk_reward','—')}</td>
                    </tr>
                </table>
                <div style="font-size:11px;margin-bottom:6px">
                    <span style="font-family:monospace;color:#4a5a6a;font-size:9px">📊 MACRO</span><br>
                    {p.get('thesis_macro','')}
                </div>
                <div style="font-size:11px;margin-bottom:6px">
                    <span style="font-family:monospace;color:#4a5a6a;font-size:9px">📈 TECHNICAL</span><br>
                    {p.get('thesis_technical','')}
                </div>
                <div style="font-size:11px;margin-bottom:6px">
                    <span style="font-family:monospace;color:#4a5a6a;font-size:9px">⚡ CATALYST</span><br>
                    {p.get('thesis_catalyst','')}
                </div>
                {prob_html}
            </div>
        </div>"""

    themes_html = ''.join(f'<span style="display:inline-block;font-family:monospace;font-size:9px;padding:2px 7px;border:1px solid #243040;color:#4a5a6a;margin:2px">{t}</span>' for t in themes)
    risks_html = ''.join(f'<div style="padding:4px 0;font-size:12px;color:#b8c8d8">→ {r}</div>' for r in risks)
    total_deployed = sum(float(p.get('position_size_usd', 0)) for p in picks)

    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
    <style>{CSS}</style></head><body><div class="wrap">
        <div class="header">
            <div class="logo">▸ Market Intelligence</div>
            <div class="title">Morning Brief</div>
            <div class="date">{DATE_STR} &nbsp;·&nbsp;
                <span style="color:{sc};font-weight:700">{sent_label}</span>
            </div>
        </div>

        <div class="card">
            <div class="card-hdr"><div class="card-lbl">Market Snapshot</div></div>
            <div class="snap-grid">{snap_html}</div>
            <div style="padding:9px 13px;border-top:1px solid #1c2530">{themes_html}</div>
        </div>

        <div class="card">
            <div class="card-hdr">
                <div class="card-lbl">Portfolio Picks — {fmt_usd(total_deployed)} nasazeno</div>
            </div>
            <div class="card-body">{picks_html}</div>
        </div>

        <div class="card">
            <div class="card-hdr"><div class="card-lbl">Klíčová rizika</div></div>
            <div class="card-body">{risks_html}</div>
        </div>

        <div style="text-align:center;padding:20px 0">
            <a href="{DASHBOARD_URL}" class="btn">Otevřít Dashboard →</a>
        </div>

        <div class="footer">
            ⚠ AI-generované projekce pouze pro vzdělávací účely. NENÍ investiční doporučení.<br>
            Automaticky generováno · Market Morning Brief · {DATE_STR}
        </div>
    </div></body></html>"""

# ── EVENING EMAIL ──────────────────────────────────────────────────────────────
def build_evening_html():
    if not review:
        return None

    picks_review = review.get('picks_review', [])
    ps = review.get('portfolio_summary', {})
    pnl_usd = ps.get('total_pnl_usd', 0)
    pnl_color = '#00d4aa' if float(pnl_usd) >= 0 else '#ff4060'
    grade = review.get('overall_grade', '?')
    grade_color = {'A':'#00d4aa','B':'#4da6ff','C':'#ffb300','D':'#ff4060','F':'#ff4060'}.get(grade,'#4a5a6a')
    hit_rate = review.get('hit_rate', 0)

    picks_html = ''
    for p in picks_review:
        oc = outcome_color(p.get('outcome',''))
        ol = outcome_label(p.get('outcome',''))
        pnl_u = float(p.get('pnl_usd', 0))
        pnl_p = float(p.get('pnl_pct', 0))
        pc = '#00d4aa' if pnl_u >= 0 else '#ff4060'
        prob = p.get('original_probability_pct')
        verdict = p.get('probability_verdict', '')
        verdict_color = {'calibrated':'#00d4aa','overconfident':'#ff4060','underconfident':'#4da6ff'}.get(verdict,'#4a5a6a')

        prob_html = ''
        if prob is not None:
            prob_html = f"""<div style="margin-top:8px;padding-top:8px;border-top:1px solid #1c2530">
                <span style="font-family:monospace;font-size:9px;color:#4a5a6a">🎲 Odhadovaná pravděpodobnost: </span>
                <span style="font-family:monospace;font-size:12px;font-weight:700;color:{prob_color(prob)}">{prob}%</span>
                {f'<span class="badge" style="color:{verdict_color};border-color:{verdict_color};margin-left:8px">{verdict.upper()}</span>' if verdict else ''}
                <div style="font-size:11px;color:#4a5a6a;margin-top:4px">{p.get('probability_comment','')}</div>
            </div>"""

        picks_html += f"""
        <div class="pick">
            <div class="pick-hdr">
                <div>
                    <div class="pick-ticker">{p.get('ticker','')}
                        <span style="font-size:10px;color:#4a5a6a;margin-left:8px">
                            {'▲ LONG' if p.get('direction')=='long' else '▼ SHORT'}
                            · Entry {fmt_usd(p.get('projected_entry',0))} → Exit {fmt_usd(p.get('exit_price') or p.get('actual_close',0))}
                        </span>
                    </div>
                </div>
                <div style="display:flex;align-items:center;gap:8px">
                    <span style="font-family:monospace;font-size:14px;font-weight:700;color:{pc}">
                        {'+' if pnl_u>=0 else ''}{fmt_usd(pnl_u)}
                        <span style="font-size:10px">{'+' if pnl_p>=0 else ''}{pnl_p:.1f}%</span>
                    </span>
                    <span class="badge" style="color:{oc};border-color:{oc}">{ol}</span>
                </div>
            </div>
            <div class="pick-body">
                <div style="font-size:12px;margin-bottom:8px">{p.get('commentary','')}</div>
                <div style="font-size:11px;margin-bottom:4px">
                    <span style="font-family:monospace;color:#4a5a6a;font-size:9px">✅ CO FUNGOVALO</span><br>
                    <span style="color:#00d4aa">{p.get('what_worked','')}</span>
                </div>
                <div style="font-size:11px;margin-bottom:4px">
                    <span style="font-family:monospace;color:#4a5a6a;font-size:9px">❌ CO SELHALO</span><br>
                    <span style="color:#ff4060">{p.get('what_failed','') if p.get('what_failed','') != 'n/a' else '—'}</span>
                </div>
                {prob_html}
            </div>
        </div>"""

    lessons_html = ''.join(f'<div style="padding:4px 0;font-size:12px;color:#b8c8d8">→ {l}</div>' for l in review.get('lessons', []))
    tomorrow_html = ''.join(f'<div style="padding:4px 0;font-size:12px;color:#b8c8d8">→ {t}</div>' for t in review.get('tomorrow_watch', []))

    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
    <style>{CSS}</style></head><body><div class="wrap">
        <div class="header">
            <div class="logo">▸ Market Intelligence</div>
            <div class="title">Evening Review</div>
            <div class="date">{DATE_STR}</div>
        </div>

        <div class="card">
            <div class="card-hdr">
                <div class="card-lbl">Session Scorecard</div>
            </div>
            <div class="card-body">
                <div style="display:flex;align-items:center;gap:24px;margin-bottom:12px">
                    <div style="text-align:center;width:60px;height:60px;border:3px solid {grade_color};display:flex;align-items:center;justify-content:center">
                        <span style="font-family:monospace;font-size:28px;font-weight:700;color:{grade_color}">{grade}</span>
                    </div>
                    <div>
                        <div style="font-family:monospace;font-size:22px;font-weight:700;color:{pnl_color}">
                            {'+' if float(pnl_usd)>=0 else ''}{fmt_usd(pnl_usd)}
                        </div>
                        <div style="font-family:monospace;font-size:11px;color:#4a5a6a">
                            Hit rate: {hit_rate}% · Score: {review.get('overall_score','?')}/100
                        </div>
                        <div style="font-size:12px;color:#4a5a6a;margin-top:4px">{review.get('index_recap','')}</div>
                    </div>
                </div>
                <div class="prose">{''.join(f'<p>{l}</p>' for l in review.get('narrative','').split('\n') if l.strip())}</div>
            </div>
        </div>

        <div class="card">
            <div class="card-hdr"><div class="card-lbl">Trade Outcomes</div></div>
            <div class="card-body">{picks_html}</div>
        </div>

        <div class="card">
            <div class="card-hdr"><div class="card-lbl">Lekce</div></div>
            <div class="card-body">{lessons_html}</div>
        </div>

        <div class="card">
            <div class="card-hdr"><div class="card-lbl">Sledovat zítra</div></div>
            <div class="card-body">{tomorrow_html}</div>
        </div>

        <div style="text-align:center;padding:20px 0">
            <a href="{DASHBOARD_URL}" class="btn">Otevřít Dashboard →</a>
        </div>

        <div class="footer">
            ⚠ AI-generované projekce pouze pro vzdělávací účely. NENÍ investiční doporučení.<br>
            Automaticky generováno · Market Morning Brief · {DATE_STR}
        </div>
    </div></body></html>"""

# ── Odeslání ───────────────────────────────────────────────────────────────────
def send_email(subject, html_body):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From']    = GMAIL_ADDRESS
    msg['To']      = GMAIL_ADDRESS
    msg.attach(MIMEText(html_body, 'html'))

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, GMAIL_ADDRESS, msg.as_string())

if RUN_MODE == 'morning':
    if not brief:
        print("⚠️  Žádný brief, email neposlán.")
        sys.exit(0)
    sentiment = brief.get('overall_sentiment', 'neutral')
    sent_emoji = {'bullish': '🟢', 'bearish': '🔴'}.get(sentiment, '🟡')
    picks = brief.get('picks', [])
    tickers = ', '.join(p.get('ticker','') for p in picks)
    subject = f"{sent_emoji} Morning Brief {DATE_KEY} · {tickers}"
    html = build_morning_html()
    send_email(subject, html)
    print(f"✅ Morning email odeslán: {subject}")

elif RUN_MODE == 'evening':
    if not review:
        print("⚠️  Žádný review, email neposlán.")
        sys.exit(0)
    grade = review.get('overall_grade', '?')
    ps = review.get('portfolio_summary', {})
    pnl = float(ps.get('total_pnl_usd', 0))
    pnl_str = f"+${pnl:,.0f}" if pnl >= 0 else f"-${abs(pnl):,.0f}"
    subject = f"📊 Evening Review {DATE_KEY} · Grade: {grade} · P&L: {pnl_str}"
    html = build_evening_html()
    if html:
        send_email(subject, html)
        print(f"✅ Evening email odeslán: {subject}")
    else:
        print("⚠️  Nepodařilo se sestavit evening email.")
