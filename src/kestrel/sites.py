from __future__ import annotations
import json
import os
import urllib.request
from pathlib import Path

HOME = Path.home()
DATA = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share")) / "kestrel"
CONF = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config")) / "kestrel"
CACHE = Path(os.environ.get("XDG_CACHE_HOME", HOME / ".cache")) / "kestrel"
WMN_URL = "https://raw.githubusercontent.com/WebBreacher/WhatsMyName/main/wmn-data.json"

# Site schema: name, url ("{}" = nickname), cat, known (real accounts for `verify`),
# optional: show_url, redirects (false = do not follow), exists_text/exists_status,
# missing_text/missing_status. Everything optional is a hint: the baseline engine works without it.
CORE = [
    {"name": "GitHub", "url": "https://github.com/{}", "cat": "coding", "known": ["torvalds"]},
    {"name": "GitLab", "url": "https://gitlab.com/{}", "cat": "coding", "known": ["torvalds"], "redirects": False},
    {"name": "Codeberg", "url": "https://codeberg.org/{}", "cat": "coding", "known": ["torvalds"]},
    {"name": "Bitbucket", "url": "https://bitbucket.org/{}/", "cat": "coding", "known": ["atlassian"]},
    {"name": "Docker Hub", "url": "https://hub.docker.com/v2/users/{}/", "cat": "coding",
     "show_url": "https://hub.docker.com/u/{}", "known": ["torvalds"]},
    {"name": "Hacker News", "url": "https://hacker-news.firebaseio.com/v0/user/{}.json", "cat": "tech",
     "show_url": "https://news.ycombinator.com/user?id={}", "known": ["pg"]},
    {"name": "Dev.to", "url": "https://dev.to/{}", "cat": "coding", "known": ["ben"]},
    {"name": "Keybase", "url": "https://keybase.io/{}", "cat": "social", "known": ["chris"]},
    {"name": "Lichess", "url": "https://lichess.org/api/user/{}", "cat": "gaming",
     "show_url": "https://lichess.org/@/{}", "known": ["torvalds"]},
    {"name": "Chess.com", "url": "https://api.chess.com/pub/player/{}", "cat": "gaming",
     "show_url": "https://www.chess.com/member/{}", "known": ["hikaru"]},
    {"name": "Wikipedia", "url": "https://en.wikipedia.org/wiki/User:{}", "cat": "news", "known": ["Jimbo_Wales"]},
]


def disabled() -> set[str]:
    try:
        return {l.strip().lower() for l in (CONF / "disabled.txt").read_text(encoding="utf-8").splitlines() if l.strip()}
    except OSError:
        return set()


def load_sites(cats: set[str] | None = None, use_disabled: bool = True) -> list[dict]:
    pool: list[dict] = []
    files = [*sorted((CONF / "sites").glob("*.json")), None, *sorted((DATA / "sites").glob("*.json"))]
    for f in files:
        if f is None:
            pool += CORE
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            pool += d if isinstance(d, list) else d.get("sites", [])
        except Exception:
            continue
    off = disabled() if use_disabled else set()
    seen, out = set(), []
    for s in pool:
        name = s.get("name")
        if not name or "{}" not in s.get("url", ""):
            continue
        k = name.lower()
        if k in seen or k in off:
            continue
        seen.add(k)
        if cats and s.get("cat", "").lower() not in cats:
            continue
        out.append(s)
    return out


def import_wmn(nsfw: bool = False) -> int:
    req = urllib.request.Request(WMN_URL, headers={"User-Agent": "kestrel"})
    data = json.loads(urllib.request.urlopen(req, timeout=60).read().decode("utf-8"))
    out = []
    for s in data.get("sites", []):
        if "uri_check" not in s or s.get("post_body"):
            continue
        if not nsfw and "NSFW" in s.get("cat", ""):
            continue
        show = (s.get("uri_pretty") or "").replace("{account}", "{}")
        out.append({
            "name": s["name"], "url": s["uri_check"].replace("{account}", "{}"),
            "show_url": show or None, "cat": s.get("cat", ""), "known": s.get("known") or [],
            "exists_status": s.get("e_code"), "exists_text": s.get("e_string") or None,
            "missing_status": s.get("m_code"), "missing_text": s.get("m_string") or None,
            "source": "WhatsMyName (CC BY-SA 4.0)",
        })
    (DATA / "sites").mkdir(parents=True, exist_ok=True)
    (DATA / "sites" / "wmn.json").write_text(json.dumps(out), encoding="utf-8")
    return len(out)
