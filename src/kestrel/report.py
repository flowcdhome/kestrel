from __future__ import annotations
import csv
import html
import json
from datetime import datetime, timezone
from pathlib import Path

from . import __version__


def to_json(path, hits, stats):
    doc = {"tool": "kestrel", "version": __version__,
           "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "stats": stats, "results": hits}
    Path(path).write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")


def to_csv(path, hits):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["nick", "site", "category", "confidence", "url", "title", "reasons"])
        for nick, rows in hits.items():
            for r in rows:
                w.writerow([nick, r["site"], r["cat"], r["confidence"], r["url"],
                            r["meta"].get("title", ""), "; ".join(r["reasons"])])


def to_html(path, hits):
    e = html.escape
    body = ""
    for nick, rows in hits.items():
        body += f"<h2>{e(nick)} <small>({len(rows)})</small></h2><table><tr><th>Conf</th><th>Site</th><th>Category</th><th>Profile</th></tr>"
        for r in rows:
            m = r["meta"]
            extra = " | ".join(e(x[:120]) for x in (m.get("title", ""), m.get("description", "")) if x)
            body += (f"<tr><td class=c>{r['confidence']}</td><td>{e(r['site'])}</td><td>{e(r['cat'])}</td>"
                     f"<td><a href=\"{e(r['url'])}\" rel=\"noreferrer\">{e(r['url'])}</a>"
                     f"<div class=m>{extra}</div></td></tr>")
        body += "</table>"
    page = f"""<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kestrel report</title>
<style>
:root{{--bg:#fff;--fg:#1a1a1a;--mut:#666;--line:#ddd;--acc:#1a7f37}}
@media(prefers-color-scheme:dark){{:root{{--bg:#11111b;--fg:#cdd6f4;--mut:#8b8fa8;--line:#2a2a3c;--acc:#a6e3a1}}}}
body{{background:var(--bg);color:var(--fg);font:15px system-ui,sans-serif;max-width:1000px;margin:2em auto;padding:0 1em}}
table{{border-collapse:collapse;width:100%;margin-bottom:2em}}td,th{{border-bottom:1px solid var(--line);padding:6px 10px;text-align:left;vertical-align:top}}
.c{{color:var(--acc);font-weight:700}}.m{{color:var(--mut);font-size:13px}}a{{color:inherit;word-break:break-all}}small{{color:var(--mut)}}
</style>
<h1>Kestrel report</h1><p class=m>Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}. A found profile does not prove it belongs to the person you are looking for.</p>
{body}"""
    Path(path).write_text(page, encoding="utf-8")
