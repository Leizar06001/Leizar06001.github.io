#!/usr/bin/env python3
"""
build.py — génère le blog de veille à partir de state.json (déterministe, stdlib only).
Produit :  posts/veille-AAAA-MM-JJ.html  ·  index.html  ·  feed.xml
Met à jour posts_index.json (manifeste des éditions, pour l'archive et le RSS).
"""
import json, os, glob, html, datetime, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(ROOT, "state.json")
POSTS_DIR = os.path.join(ROOT, "posts")
INDEX_JSON = os.path.join(ROOT, "posts_index.json")

HZ_TITLES = {
    "T-0": ("T-0 · 2026 – 2027 · Imminent", "Les rails se posent"),
    "T-1": ("T-1 · 2027 – 2029 · Verrouillage", "Fermeture des sorties"),
    "T-2": ("T-2 · 2029 – 2035 · Activation", "Convergence + choc"),
    "T-3": ("T-3 · 2035 – 2050 · Structurel", "Les formes stables"),
}
HZ_ORDER = ["T-0", "T-1", "T-2", "T-3"]

def esc(s):
    return html.escape(str(s if s is not None else ""))

# ---------- sparkline depuis prob_history ----------
def sparkline(history, color):
    pts = [h["prob"] for h in history if isinstance(h.get("prob"), (int, float))]
    W, H, pad = 74, 22, 3
    if not pts:
        return ""
    if len(pts) == 1:
        pts = pts * 2
    lo, hi = min(pts), max(pts)
    span = (hi - lo) or 1
    n = len(pts)
    coords = []
    for i, p in enumerate(pts):
        x = pad + (W - 2 * pad) * (i / (n - 1))
        y = (H - pad) - (H - 2 * pad) * ((p - lo) / span)
        coords.append(f"{x:.0f},{y:.0f}")
    return (f'<svg class="spark" viewBox="0 0 {W} {H}"><polyline points="{" ".join(coords)}" '
            f'fill="none" stroke="{color}" stroke-width="1.6"/></svg>')

def delta_today(sig, today):
    lc = sig.get("last_change")
    if lc and lc.get("date") == today and isinstance(lc.get("delta"), (int, float)):
        return lc["delta"]
    return 0

def delta_chip(d):
    if d > 0:   return f'<span class="delta up">▲ +{d}</span>', "#F2A266"
    if d < 0:   return f'<span class="delta dn">▼ {d}</span>', "#82D2E0"
    return '<span class="delta flat">→ 0</span>', "#69757F"

def prob_pill(sig):
    if not sig.get("is_bascule") or sig.get("prob") is None:
        return ""
    rng = sig.get("prob_range") or [sig["prob"], sig["prob"]]
    return f'<span class="prob">P {rng[0]}–{rng[1]}% · médiane {sig["prob"]}%</span>'

# ---------- barometre ----------
def render_barometer(signals, today):
    rows = []
    for s in signals:
        if not s.get("is_bascule") or s.get("prob") is None:
            continue
        d = delta_today(s, today)
        chip, color = delta_chip(d)
        spark = sparkline(s.get("prob_history", []), color)
        rows.append(f'''
      <div class="gauge">
        <span class="name">{esc(s["title"])}</span>
        <span class="track"><span class="fill" style="width:{s["prob"]}%"></span></span>
        <span class="pct">{s["prob"]}%</span>
        {chip}
        {spark}
      </div>''')
    if not rows:
        return ""
    return f'''<div class="baro">
      <h2>Baromètre des bascules</h2>{"".join(rows)}
    </div>'''

# ---------- carte ----------
def render_card(s, today):
    is_new = s.get("created") == today
    lc = s.get("last_change")
    is_changed = bool(lc and lc.get("date") == today and lc.get("delta") is not None)
    cls = "card"
    if is_new: cls += " is-new"
    elif is_changed: cls += " is-changed"

    badges = ""
    if is_new:
        badges = '<span class="badge new">NOUVEAU</span>'
    elif is_changed:
        d = lc["delta"]
        badges = (f'<span class="badge up">▲ +{d}</span>' if d > 0
                  else f'<span class="badge dn">▼ {d}</span>')
    elif not s.get("is_bascule"):
        badges = f'<span class="when">{esc(s.get("when",""))}</span>'

    note = ""
    if (is_new or is_changed) and lc and lc.get("reason"):
        label = "Pourquoi ajouté" if is_new else "Changement"
        links = ""
        for sid in (lc.get("sources") or []):
            links += f' <a href="#{esc(sid)}">source ↓</a>'
        note = f'<p class="changed-note"><b>{label} —</b> {esc(lc["reason"])}{links}</p>'

    pill = prob_pill(s)
    return f'''
      <article class="{cls}">
        <div class="c-top"><span class="tag">{esc(s["domain"])}</span><span class="badges">{badges}</span></div>
        <div class="c-title">{esc(s["title"])}</div>
        {pill}
        <div class="c-status">{esc(s["status"])}</div>
        {note}
        <div class="dir">
          <div class="row up"><span class="ic">▲</span><span class="txt"><strong>Aggrave —</strong> {esc(s["up"])}</span></div>
          <div class="row dn"><span class="ic">▼</span><span class="txt"><strong>Freine —</strong> {esc(s["down"])}</span></div>
        </div>
      </article>'''

def render_horizons(signals, today):
    out = []
    for hz in HZ_ORDER:
        group = [s for s in signals if s.get("horizon") == hz]
        if not group:
            continue
        tag, title = HZ_TITLES[hz]
        cards = "".join(render_card(s, today) for s in group)
        out.append(f'''
  <section class="horizon">
    <div class="hz-head"><div class="hz-tag">{esc(tag)}</div><div class="hz-title">{esc(title)}</div></div>
    <div class="grid">{cards}</div>
  </section>''')
    return "".join(out)

# ---------- sources ----------
def render_sources(state):
    srcs = state.get("sources_today", [])
    by_id = {s["id"]: s for s in state["signals"]}
    if not srcs:
        body = '<p class="sub">Aucune actualité significative aujourd\'hui — la veille tourne, sans mouvement artificiel.</p>'
    else:
        rows = []
        for src in srcs:
            affects = src.get("affects") or []
            names = ", ".join(by_id[a]["title"] for a in affects if a in by_id) or "—"
            rows.append(f'''
    <div class="src" id="{esc(src["id"])}">
      <div class="meta"><span class="name">{esc(src["name"])}</span>{esc(src["date"])}</div>
      <div class="body">
        <div class="t">{esc(src["title"])}</div>
        <div class="d">{esc(src.get("summary",""))}</div>
        <div class="ln"><a href="{esc(src["url"])}" target="_blank" rel="noopener">Ouvrir ↗</a><span class="affects">affecte → <b>{esc(names)}</b></span></div>
      </div>
    </div>''')
        body = ('<p class="sub">Les actualités qui ont influencé les prédictions modifiées ou ajoutées aujourd\'hui.</p>'
                + "".join(rows))
    return f'''<section class="sources"><h2>Sources du jour</h2>{body}</section>'''

# ---------- tuiles + diff line ----------
def render_header(state, prev_date):
    ts = state["today_summary"]
    today = state["last_updated"]
    d = datetime.date.fromisoformat(today)
    months = ["janvier","février","mars","avril","mai","juin","juillet","août",
              "septembre","octobre","novembre","décembre"]
    pretty = f"{d.day} {months[d.month-1]} {d.year}"
    arrow = {"up":"▲","down":"▼","flat":"→"}.get(ts.get("trend","flat"),"→")
    diff = (f'<b>Aujourd\'hui —</b> '
            f'<span class="c-chg">{ts["changed"]} modifiées</span> · '
            f'<span class="c-new">{ts["new"]} nouvelle(s)</span> · '
            f'<span class="c-up">↑ {ts["up"]} en hausse</span> · '
            f'<span class="c-dn">↓ {ts["down"]} en baisse</span> · '
            f'{ts["stable"]} stables')
    return pretty, arrow, diff

PAGE = '''<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Veille · Édition du {pretty}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>{css}</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="eyebrow"><span class="dot" aria-hidden="true"></span><span>Veille · Convergence numérique</span><span>·</span><span>Édition quotidienne</span></div>
    <h1>Édition du <span class="date">{pretty}</span></h1>
    <p class="diff-line">{diff}</p>
    <div class="quick">
      <div class="tile chg"><div class="v">{changed}</div><div class="l">Modifiées</div></div>
      <div class="tile new"><div class="v">{new}</div><div class="l">Nouvelle(s)</div></div>
      <div class="tile"><div class="v">{nsrc}</div><div class="l">Sources du jour</div></div>
      <div class="tile trend"><div class="v"><span class="arr">{arrow}</span> {trend_label}</div><div class="l">Tendance</div></div>
    </div>
    {barometer}
    <div class="legend">
      <span><span class="chip-demo n">NOUVEAU</span> ajoutée aujourd'hui</span>
      <span><span class="chip-demo u">▲ +n</span> en hausse (escalade)</span>
      <span><span class="chip-demo d">▼ −n</span> en baisse (apaisement)</span>
      <span><span class="bar up"></span> aggrave / <span class="bar dn"></span> freine</span>
    </div>
  </header>
  {horizons}
  {sources}
  <div class="foot">
    <p>Les pourcentages sont des jugements structurés, pas des prévisions calibrées. Une probabilité ne bouge que sur un fait déclencheur matériel, sourcé, avec un delta plafonné.</p>
    <div class="nav">
      <a href="../index.html">← Archive</a>
      {prev_link}
      <a href="../feed.xml">RSS</a>
    </div>
    <p class="stamp">Généré le {pretty} · sources publiques</p>
  </div>
</div>
</body>
</html>'''

def build_page(state, css):
    today = state["last_updated"]
    prev_date = previous_date(today)
    pretty, arrow, diff = render_header(state, prev_date)
    ts = state["today_summary"]
    prev_link = (f'<a href="./veille-{prev_date}.html">Édition précédente</a>'
                 if prev_date else "")
    html_out = PAGE.format(
        pretty=esc(pretty), css=css, diff=diff,
        changed=ts["changed"], new=ts["new"], nsrc=len(state.get("sources_today", [])),
        arrow=arrow, trend_label=esc(ts.get("trend_label","")),
        barometer=render_barometer(state["signals"], today),
        horizons=render_horizons(state["signals"], today),
        sources=render_sources(state),
        prev_link=prev_link,
    )
    os.makedirs(POSTS_DIR, exist_ok=True)
    with open(os.path.join(POSTS_DIR, f"veille-{today}.html"), "w", encoding="utf-8") as f:
        f.write(html_out)
    return today

# ---------- manifeste / archive / RSS ----------
def load_index():
    if os.path.exists(INDEX_JSON):
        with open(INDEX_JSON, encoding="utf-8") as f:
            return json.load(f)
    return []

def upsert_index(state):
    idx = load_index()
    today = state["last_updated"]
    ts = state["today_summary"]
    entry = {"date": today, "changed": ts["changed"], "new": ts["new"],
             "up": ts["up"], "down": ts["down"], "stable": ts["stable"],
             "trend_label": ts.get("trend_label","")}
    idx = [e for e in idx if e["date"] != today] + [entry]
    idx.sort(key=lambda e: e["date"], reverse=True)
    with open(INDEX_JSON, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)
    return idx

def previous_date(today):
    idx = load_index()
    earlier = sorted([e["date"] for e in idx if e["date"] < today], reverse=True)
    return earlier[0] if earlier else None

def build_archive(state, idx, css):
    rows = []
    for e in idx:
        trend = e.get("trend_label", "")
        rows.append(f'''
      <a class="arow" href="posts/veille-{e["date"]}.html">
        <span class="ad">{esc(e["date"])}</span>
        <span class="as"><b>{e["changed"]}</b> modifiées · <b>{e["new"]}</b> nouvelle(s) · {e["stable"]} stables</span>
        <span class="atag">{esc(trend)}</span>
      </a>''')
    page = f'''<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(state["meta"]["title"])} · Archive</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>{css}
.alist{{margin-top:30px;display:flex;flex-direction:column;gap:0}}
.arow{{display:grid;grid-template-columns:160px 1fr auto;gap:16px;align-items:baseline;
  padding:14px 8px;border-top:1px solid var(--line-soft);text-decoration:none;
  border-radius:8px;transition:background .18s}}
.arow:hover{{background:var(--panel)}}
.ad{{font-family:'IBM Plex Mono',monospace;color:var(--ember-bright);font-size:13px}}
.as{{color:var(--text-2);font-size:13px}}.as b{{color:var(--text)}}
.atag{{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--text-3);
  border:1px solid var(--line);border-radius:5px;padding:2px 7px;white-space:nowrap;align-self:center}}
@media(max-width:600px){{.arow{{grid-template-columns:1fr}}.atag{{display:none}}}}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="eyebrow">
      <span class="dot" aria-hidden="true"></span>
      <span>Veille · Convergence numérique</span>
      <span>·</span><span>Archive</span>
    </div>
    <h1>Éditions <em style="color:var(--text-2);font-weight:500">quotidiennes</em></h1>
    <p class="diff-line" style="margin-top:14px">
      Une page par jour — prédictions affinées à chaque actualité matérielle sourcée.
      <b>{len(idx)}</b> édition(s) publiée(s).
    </p>
  </header>
  <div class="alist">{"".join(rows)}</div>
  <div class="foot">
    <div class="nav">
      <a href="feed.xml">RSS</a>
      {f'<a href="posts/veille-{idx[0]["date"]}.html">Dernière édition →</a>' if idx else ""}
    </div>
    <p class="stamp">Mis à jour le {esc(state["last_updated"])}</p>
  </div>
</div>
</body>
</html>'''
    with open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)

def build_feed(state, idx):
    base = state["meta"].get("base_url", "").rstrip("/")
    title = esc(state["meta"]["title"])
    items = []
    for e in idx[:30]:
        d = datetime.date.fromisoformat(e["date"])
        pub = d.strftime("%a, %d %b %Y 06:00:00 +0000")
        link = f"{base}/posts/veille-{e['date']}.html"
        desc = f'{e["changed"]} prédictions modifiées, {e["new"]} nouvelle(s), {e["stable"]} stables.'
        items.append(f'''  <item>
    <title>Édition du {esc(e["date"])}</title>
    <link>{esc(link)}</link>
    <guid>{esc(link)}</guid>
    <pubDate>{pub}</pubDate>
    <description>{esc(desc)}</description>
  </item>''')
    feed = f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>{title}</title>
  <link>{esc(base)}</link>
  <description>Veille quotidienne sur la convergence numérique.</description>
  <language>fr</language>
{chr(10).join(items)}
</channel></rss>'''
    with open(os.path.join(ROOT, "feed.xml"), "w", encoding="utf-8") as f:
        f.write(feed)

def main():
    with open(STATE, encoding="utf-8") as f:
        state = json.load(f)
    css_path = os.path.join(ROOT, "style.css")
    with open(css_path, encoding="utf-8") as f:
        css = f.read()
    build_page(state, css)
    idx = upsert_index(state)
    build_archive(state, idx, css)
    build_feed(state, idx)
    print(f"OK · édition {state['last_updated']} · {len(idx)} éditions au total")

if __name__ == "__main__":
    main()