from __future__ import annotations
import json
import urllib.request

from .sites import DATA, import_wmn

SRC = {
    "sherlock": ["https://raw.githubusercontent.com/sherlock-project/sherlock/master/sherlock_project/resources/data.json",
                 "https://raw.githubusercontent.com/sherlock-project/sherlock/master/sherlock/resources/data.json",
                 "https://raw.githubusercontent.com/sherlock-project/sherlock/main/sherlock_project/resources/data.json"],
    "maigret": "https://raw.githubusercontent.com/soxoj/maigret/main/maigret/resources/data.json",
}


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "kestrel"})
    return json.loads(urllib.request.urlopen(req, timeout=90).read().decode("utf-8"))


def _save(name, sites):
    (DATA / "sites").mkdir(parents=True, exist_ok=True)
    (DATA / "sites" / f"{name}.json").write_text(json.dumps(sites), encoding="utf-8")
    return len(sites)


def import_sherlock(nsfw=False):
    data, err = None, None
    for u in SRC["sherlock"]:
        try:
            data = _get(u)
            break
        except Exception as e:
            err = e
    if data is None:
        raise err
    data.pop("$schema", None)
    out = []
    for name, s in data.items():
        if not isinstance(s, dict) or (s.get("isNSFW") and not nsfw):
            continue
        probe = s.get("urlProbe") or s.get("url")
        if not probe or "{}" not in probe:
            continue
        shown = s.get("url") or probe
        item = {"name": name, "url": probe, "show_url": shown if shown != probe else None,
                "cat": "", "regex": s.get("regexCheck"),
                "known": [s["username_claimed"]] if s.get("username_claimed") else [],
                "source": "Sherlock (MIT)"}
        et = s.get("errorType")
        ets = et if isinstance(et, list) else [et]
        if "response_url" in ets:
            item["redirects"] = False
        if "message" in ets and s.get("errorMsg"):
            item["missing_text"] = s["errorMsg"]
        out.append(item)
    return _save("sherlock", out)


def import_maigret(nsfw=False):
    data = _get(SRC["maigret"])
    engines = data.get("engines", {})
    out = []
    for name, s in data.get("sites", {}).items():
        if not isinstance(s, dict) or s.get("disabled"):
            continue
        m = {}
        eng = engines.get(s.get("engine"))
        if eng:
            m.update(eng.get("site", {}))
        m.update(s)

        def fix(u):
            if not u:
                return None
            u = (u.replace("{urlMain}", m.get("urlMain", "")).replace("{urlSubpath}", m.get("urlSubpath", ""))
                  .replace("{username}", "{}"))
            return u if "{}" in u and "{" not in u.replace("{}", "") else None

        url, probe = fix(m.get("url")), fix(m.get("urlProbe"))
        if not (probe or url):
            continue
        tags = [t for t in m.get("tags", []) if isinstance(t, str)]
        if not nsfw and any(t in ("porn", "erotic", "adult") for t in tags):
            continue
        item = {"name": name, "url": probe or url, "show_url": url if probe and url != probe else None,
                "cat": next((t for t in tags if len(t) > 2), ""), "regex": m.get("regexCheck"),
                "known": [m["usernameClaimed"]] if m.get("usernameClaimed") else [],
                "rank": m.get("alexaRank"), "source": "Maigret (MIT)"}
        ct = m.get("checkType")
        if ct == "response_url":
            item["redirects"] = False
        elif ct == "message" and m.get("absenceStrs"):
            item["missing_text"] = m["absenceStrs"]
        out.append(item)
    return _save("maigret", out)


def import_all(console, nsfw=False):
    total = 0
    for label, fn in (("Sherlock", import_sherlock), ("WhatsMyName", import_wmn), ("Maigret", import_maigret)):
        try:
            n = fn(nsfw)
            total += n
            console.print(f"[green]+ {label}: {n} sites[/]")
        except Exception as e:
            console.print(f"[red]- {label}: failed ({type(e).__name__}: {e})[/]")
    console.print(f"[bold]{total} entries downloaded[/] (duplicates are merged at load time). "
                  "Next: kestrel verify --apply")
