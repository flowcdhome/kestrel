from __future__ import annotations
import argparse
import asyncio
import re
import sys
import time
from collections import Counter

from rich.console import Console
from rich.markup import escape
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

from . import __version__, report
from .engine import Engine, rand_nick
from .sites import CONF, import_wmn, load_sites
from .importers import import_all

console = Console()
SUBS = {"verify", "import-wmn", "sites"}


def variants(raw: str) -> list[str]:
    raw = raw.strip()
    parts = [p for p in re.split(r"[\s._\-]+", raw) if p]
    out = [raw]
    if len(parts) >= 2:
        a, b = parts[0], parts[-1]
        for sep in ("", ".", "_", "-"):
            out += [a + sep + b, b + sep + a]
        out += [a[0] + b, a + b[0], b + a[0]]
    seen, res = set(), []
    for v in out:
        v = v.lower() if " " in raw else v
        if len(v) >= 3 and " " not in v and v not in seen:
            seen.add(v)
            res.append(v)
    return res


def progress():
    return Progress(SpinnerColumn(), TextColumn("{task.description}"), BarColumn(), MofNCompleteColumn(),
                    console=console, transient=True)


async def run_search(nicks, sites, a):
    eng = Engine(proxy=a.proxy, concurrency=a.concurrency, timeout=a.timeout, use_cache=not a.no_cache)
    out = {}
    try:
        for nick in nicks:
            with progress() as prog:
                task = prog.add_task(escape(nick), total=len(sites))
                found = [0]

                def cb(r):
                    if r["state"] == "found" and r["confidence"] >= a.min_confidence:
                        found[0] += 1
                    prog.update(task, advance=1, description=f"{escape(nick)}  [green]found: {found[0]}[/]")
                out[nick] = await eng.scan(sites, nick, cb)
    finally:
        await eng.close()
    return out


def show(nick, res, a):
    found = sorted((r for r in res if r["state"] == "found" and r["confidence"] >= a.min_confidence),
                   key=lambda r: (-r["confidence"], r["site"].lower()))
    unknown = sum(1 for r in res if r["state"] == "unknown")
    missing = sum(1 for r in res if r["state"] == "missing")
    t = Table(title=f"{escape(nick)}: {len(found)} profiles")
    t.add_column("Conf", justify="right")
    t.add_column("Site")
    t.add_column("Category", style="dim")
    t.add_column("URL", overflow="fold")
    for r in found:
        c = r["confidence"]
        t.add_row(f"[{'green' if c >= 70 else 'yellow'}]{c}[/]", escape(r["site"]), escape(r["cat"]), escape(r["url"]))
        if a.details:
            m = r["meta"]
            line = " | ".join(x[:100] for x in (m.get("title", ""), m.get("description", "")) if x)
            if line:
                t.add_row("", "", "", f"[dim]{escape(line)}[/]")
    console.print(t)
    console.print(f"[dim]not found: {missing} | unknown (blocked or inconclusive): {unknown}[/]")
    return found, {"found": len(found), "missing": missing, "unknown": unknown}


def search_main(argv):
    p = argparse.ArgumentParser(
        prog="kestrel", description="Kestrel: username search with baseline-differential detection",
        epilog="subcommands: verify | import-wmn | sites   (kestrel verify -h)")
    p.add_argument("nicks", nargs="*", help="one or more nicknames")
    p.add_argument("-V", "--version", action="version", version=f"kestrel {__version__}")
    p.add_argument("--variants", action="store_true", help="also try variants (john doe -> johndoe, john.doe, jdoe...)")
    p.add_argument("--cat", action="append", help="only this category (repeatable)")
    p.add_argument("--top", type=int, help="only the N most popular sites (ranked sites first)")
    p.add_argument("--min-confidence", type=int, default=40, help="hide hits below this score (default 40)")
    p.add_argument("--details", action="store_true", help="show profile title/description")
    p.add_argument("--proxy", help="e.g. socks5://127.0.0.1:1080 or http://host:port")
    p.add_argument("--tor", action="store_true", help="shortcut for --proxy socks5://127.0.0.1:9050")
    p.add_argument("--timeout", type=float, default=10.0)
    p.add_argument("--concurrency", type=int, default=40)
    p.add_argument("--no-cache", action="store_true", help="re-learn baselines instead of using the 24h cache")
    p.add_argument("--json", metavar="FILE")
    p.add_argument("--csv", metavar="FILE")
    p.add_argument("--html", metavar="FILE")
    a = p.parse_args(argv)
    if not a.nicks:
        p.print_help()
        return
    if a.tor:
        a.proxy = "socks5://127.0.0.1:9050"
    sites = load_sites({c.lower() for c in a.cat} if a.cat else None)
    if a.top:
        sites = sorted(sites, key=lambda s: s.get('rank') or 10**9)[:a.top]
    if not sites:
        return console.print("[red]no sites loaded[/] (try: kestrel import-wmn, or check --cat)")
    nicks = []
    for n in a.nicks:
        nicks += variants(n) if a.variants else [n]
    nicks = list(dict.fromkeys(nicks))
    console.print(f"[bold]kestrel[/] | {len(sites)} sites | {len(nicks)} nick(s)")
    t0 = time.time()
    results = asyncio.run(run_search(nicks, sites, a))
    hits, stats = {}, {}
    for nick, res in results.items():
        hits[nick], stats[nick] = show(nick, res, a)
    console.print(f"[dim]done in {time.time() - t0:.0f}s. A found profile does not prove it belongs to the person you look for.[/]")
    if a.json:
        report.to_json(a.json, hits, stats)
    if a.csv:
        report.to_csv(a.csv, hits)
    if a.html:
        report.to_html(a.html, hits)
    for name, path in (("JSON", a.json), ("CSV", a.csv), ("HTML", a.html)):
        if path:
            console.print(f"saved {name}: {path}")


async def run_verify(sites, a):
    eng = Engine(proxy=a.proxy, concurrency=a.concurrency, timeout=a.timeout, use_cache=False)

    async def one(s):
        known = s.get("known") or []
        if not known:
            return s["name"], "no-known", ""
        hit = await eng.check(s, known[0])
        miss = await eng.check(s, rand_nick())
        if miss["state"] == "found":
            return s["name"], "false-positive", f"random nick looks found ({'; '.join(miss['reasons'])})"
        if hit["state"] != "found":
            return s["name"], "misses-real", f"known '{known[0]}' -> {hit['state']} ({'; '.join(hit['reasons'])})"
        return s["name"], ("ok" if miss["state"] == "missing" else "weak"), ""

    try:
        with progress() as prog:
            task = prog.add_task("verifying", total=len(sites))

            async def wrapped(s):
                try:
                    return await one(s)
                finally:
                    prog.advance(task)
            return await asyncio.gather(*(wrapped(s) for s in sites))
    finally:
        await eng.close()


def verify_main(argv):
    p = argparse.ArgumentParser(prog="kestrel verify", description="Self-test the site database")
    p.add_argument("--apply", action="store_true", help="disable broken sites (writes ~/.config/kestrel/disabled.txt)")
    p.add_argument("--proxy")
    p.add_argument("--timeout", type=float, default=10.0)
    p.add_argument("--concurrency", type=int, default=40)
    a = p.parse_args(argv)
    sites = load_sites(use_disabled=False)
    console.print(f"[bold]verifying {len(sites)} sites[/] (known account must be found, random nick must not)")
    res = asyncio.run(run_verify(sites, a))
    cnt = Counter(r[1] for r in res)
    console.print(f"ok: [green]{cnt['ok']}[/] | weak (random nick unclear): {cnt['weak']} | "
                  f"no known account: {cnt['no-known']} | [red]false positives: {cnt['false-positive']}[/] | "
                  f"[red]misses real profile: {cnt['misses-real']}[/]")
    bad = [r for r in res if r[1] in ("false-positive", "misses-real")]
    if bad:
        t = Table(title="Problem sites")
        t.add_column("Site")
        t.add_column("Problem")
        t.add_column("Detail", overflow="fold")
        for name, kind, detail in sorted(bad):
            t.add_row(escape(name), kind, escape(detail))
        console.print(t)
        console.print("[dim]A 'known' account may also have been deleted. Use --apply to skip these sites.[/]")
    if a.apply:
        CONF.mkdir(parents=True, exist_ok=True)
        (CONF / "disabled.txt").write_text("\n".join(sorted(r[0] for r in bad)) + "\n", encoding="utf-8")
        console.print(f"disabled {len(bad)} sites in {CONF / 'disabled.txt'} (delete that file to re-enable)")


def main():
    argv = sys.argv[1:]
    try:
        if argv and argv[0] == "verify":
            verify_main(argv[1:])
        elif argv and argv[0] == "import-wmn":
            p = argparse.ArgumentParser(prog="kestrel import-wmn", description="Download 600+ sites from WhatsMyName")
            p.add_argument("--nsfw", action="store_true", help="include adult sites")
            a = p.parse_args(argv[1:])
            console.print(f"[green]imported {import_wmn(a.nsfw)} sites[/] (WhatsMyName, CC BY-SA 4.0). Next: kestrel verify --apply")
        elif argv and argv[0] == "import-all":
            p = argparse.ArgumentParser(prog="kestrel import-all", description="Download Sherlock, WhatsMyName and Maigret site lists")
            p.add_argument("--nsfw", action="store_true", help="include adult sites")
            import_all(console, p.parse_args(argv[1:]).nsfw)
        elif argv and argv[0] == "sites":
            sites = load_sites()
            c = Counter(s.get("cat", "") or "other" for s in sites)
            console.print(f"{len(sites)} sites enabled")
            for k, v in c.most_common():
                console.print(f"  {k}: {v}")
        else:
            search_main(argv)
    except KeyboardInterrupt:
        console.print("\n[yellow]interrupted[/]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[red]error:[/] {escape(str(e))}")
        sys.exit(1)


if __name__ == "__main__":
    main()
