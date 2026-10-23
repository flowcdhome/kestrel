from __future__ import annotations
import asyncio
import html
import json
import random
import re
import string
import time
import zlib
from urllib.parse import quote, urlsplit

import httpx

from .sites import CACHE

UA = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
K, TTL, MAX_BODY = 64, 24 * 3600, 300_000
BASE_FILE = CACHE / "baselines.json"
BLOCK_RE = re.compile(r"captcha|just a moment|cf-chl|attention required|access denied|are you a robot|unusual traffic", re.I)
STRIP_RE = re.compile(r"<(script|style|noscript)\b.*?</\1>", re.S | re.I)
TAG_RE = re.compile(r"<[^>]+>")
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
WORD_RE = re.compile(r"\w{3,}")


def rand_nick() -> str:
    return "zq" + "".join(random.choices(string.ascii_lowercase + string.digits, k=11))


def url_for(site: dict, nick: str, key: str = "url") -> str:
    return (site.get(key) or site["url"]).replace("{}", quote(nick, safe=""))


def norm_url(url: str, nick: str) -> str:
    u = urlsplit(url)
    s = f"{u.netloc}{u.path}"
    for v in {nick, quote(nick, safe="")}:
        s = re.sub(re.escape(v), "{n}", s, flags=re.I)
    return s.rstrip("/")


def sketch(text: str) -> list[int]:
    words = set(WORD_RE.findall(text.lower()))
    return sorted(zlib.crc32(w.encode()) for w in words)[:K]


def sim(a: list[int], b: list[int]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    sa, sb = set(a), set(b)
    u = sorted(sa | sb)[:K]
    return sum(1 for h in u if h in sa and h in sb) / len(u)


def make_fp(nick: str, status: int, final: str, text: str) -> dict:
    blocked = status in (403, 429, 503, 999) or (status >= 400 and len(text) < 30000 and bool(BLOCK_RE.search(text)))
    clean = re.sub(re.escape(nick), " ", text, flags=re.I)
    t = TITLE_RE.search(clean)
    title = re.sub(r"\s+", " ", html.unescape(t.group(1))).strip().lower() if t else ""
    body = TAG_RE.sub(" ", STRIP_RE.sub(" ", clean))
    return {"status": status, "final": norm_url(final, nick), "title": title,
            "len": len(text), "sk": sketch(body), "blocked": blocked}


def _meta(text: str, prop: str) -> str:
    head = text[:200_000]
    for pat in (rf'<meta[^>]+(?:property|name)=["\']{prop}["\'][^>]*content=["\']([^"\']*)["\']',
                rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]*(?:property|name)=["\']{prop}["\']'):
        m = re.search(pat, head, re.I)
        if m:
            return html.unescape(m.group(1)).strip()
    return ""


def extract(text: str) -> dict:
    out = {}
    t = TITLE_RE.search(text[:200_000])
    if t:
        out["title"] = re.sub(r"\s+", " ", html.unescape(t.group(1))).strip()
    d = _meta(text, "og:description") or _meta(text, "description")
    if d:
        out["description"] = d
    i = _meta(text, "og:image")
    if i:
        out["image"] = i
    return out


def judge(site: dict, nick: str, r, base):
    """Decide found / missing / unknown. Returns (state, confidence, reasons, meta)."""
    if r is None:
        return "unknown", 0, ["no response"], {}
    status, final, text = r
    fp = make_fp(nick, status, final, text)
    if fp["blocked"]:
        return "unknown", 0, [f"blocked (HTTP {status})"], {}
    mt = site.get("missing_text")
    if mt and any(m in text for m in ([mt] if isinstance(mt, str) else mt)):
        return "missing", 0, ["missing_text matched"], {}
    ms, ex, et = site.get("missing_status"), site.get("exists_status"), site.get("exists_text")
    if ms is not None and status == ms and status != ex:
        return "missing", 0, ["missing_status matched"], {}

    score, why, sig = 0, [], False
    if ex is not None or et:
        if (ex is None or status == ex) and (not et or et in text):
            sig = True
            score += 50
            why.append("site signature matched")

    b = [x for x in (base or []) if x and not x["blocked"]]
    diff = None
    if b and len({x["status"] for x in b}) == 1:
        bs, ok = b[0]["status"], 200 <= status < 300
        if bs in (404, 410):
            if ok:
                diff = True
                score += 45
                why.append(f"baseline is HTTP {bs}, profile is HTTP {status}")
            elif status in (404, 410):
                diff = False
        elif 300 <= bs < 400:
            if ok:
                diff = True
                score += 45
                why.append("baseline redirects, profile does not")
            elif 300 <= status < 400:
                diff = False
        elif 200 <= bs < 300:
            if status in (404, 410):
                diff = False
            elif ok:
                if all(x["final"] != fp["final"] for x in b):
                    diff = True
                    score += 40
                    why.append("final URL differs from baseline")
                else:
                    noise = sim(b[0]["sk"], b[1]["sk"]) if len(b) > 1 else 0.8
                    s = max(sim(fp["sk"], x["sk"]) for x in b)
                    sim_diff = s < max(0.6, noise - 0.15)
                    title_diff = all(fp["title"] != x["title"] for x in b)
                    if sim_diff and title_diff:
                        diff = True
                        score += 35
                        why.append("page content and title differ from baseline")
                    elif not sim_diff and not title_diff:
                        diff = False

    if diff is False and not sig:
        return "missing", 0, ["same as baseline"], {}
    if diff is None and not sig:
        return "unknown", 0, ["inconclusive"], {}
    meta = extract(text)
    if nick.lower() in text.lower():
        score += 20
        why.append("nickname appears on the page")
    if meta.get("image") or meta.get("description"):
        score += 10
        why.append("profile metadata present")
    return "found", min(score, 100), why, meta


async def fetch(client: httpx.AsyncClient, url: str, follow: bool):
    try:
        async with client.stream("GET", url, follow_redirects=follow) as r:
            buf = bytearray()
            async for chunk in r.aiter_bytes():
                buf += chunk
                if len(buf) > MAX_BODY:
                    break
            try:
                text = bytes(buf).decode(r.encoding or "utf-8", "replace")
            except LookupError:
                text = bytes(buf).decode("utf-8", "replace")
            return r.status_code, str(r.url), text
    except Exception:
        return None


class Engine:
    def __init__(self, proxy=None, concurrency=40, per_host=4, timeout=10.0, use_cache=True):
        self.client = httpx.AsyncClient(
            headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"},
            timeout=timeout, proxy=proxy,
            limits=httpx.Limits(max_connections=concurrency * 2, max_keepalive_connections=20))
        self.sem = asyncio.Semaphore(concurrency)
        self.per_host = per_host
        self.timeout = timeout
        self.hosts: dict[str, asyncio.Semaphore] = {}
        self.use_cache = use_cache
        try:
            self.cache = json.loads(BASE_FILE.read_text(encoding="utf-8"))
        except Exception:
            self.cache = {}

    async def get(self, url: str, follow: bool = True):
        host = urlsplit(url).netloc
        hs = self.hosts.setdefault(host, asyncio.Semaphore(self.per_host))
        async with hs, self.sem:
            for _ in range(2):
                try:
                    r = await asyncio.wait_for(fetch(self.client, url, follow), self.timeout * 1.5)
                except asyncio.TimeoutError:
                    return None
                if r:
                    return r
        return None

    async def baseline(self, site: dict):
        key = site["url"]
        c = self.cache.get(key)
        if self.use_cache and c and time.time() - c["t"] < TTL:
            return c["fps"]
        follow = site.get("redirects", True)
        nicks = [rand_nick(), rand_nick()]
        rs = await asyncio.gather(*(self.get(url_for(site, n), follow) for n in nicks))
        fps = [make_fp(n, *r) if r else None for n, r in zip(nicks, rs)]
        self.cache[key] = {"t": time.time(), "fps": fps}
        return fps

    async def check(self, site: dict, nick: str) -> dict:
        rx = site.get("regex")
        if rx:
            try:
                if not re.fullmatch(rx, nick):
                    return {"site": site["name"], "cat": site.get("cat", ""), "url": url_for(site, nick, "show_url"),
                            "state": "missing", "confidence": 0, "reasons": ["nick format not valid here"], "meta": {}}
            except re.error:
                pass
        try:
            r, base = await asyncio.gather(
                self.get(url_for(site, nick), site.get("redirects", True)), self.baseline(site))
            state, conf, why, meta = judge(site, nick, r, base)
        except Exception as e:
            state, conf, why, meta = "unknown", 0, [f"error: {type(e).__name__}"], {}
        return {"site": site["name"], "cat": site.get("cat", ""), "url": url_for(site, nick, "show_url"),
                "state": state, "confidence": conf, "reasons": why, "meta": meta}

    async def scan(self, sites, nick, cb=None):
        async def one(s):
            r = await self.check(s, nick)
            if cb:
                cb(r)
            return r
        return await asyncio.gather(*(one(s) for s in sites))

    async def close(self):
        await self.client.aclose()
        try:
            CACHE.mkdir(parents=True, exist_ok=True)
            BASE_FILE.write_text(json.dumps(self.cache), encoding="utf-8")
        except OSError:
            pass
