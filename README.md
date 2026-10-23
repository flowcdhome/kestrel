<div align="center">

# 🦅 Kestrel

**Username OSINT that learns what "not found" looks like on every site, and checks its own database.**

🇬🇧 English · [🇷🇺 Русский](README.ru.md)

[![Release](https://img.shields.io/github/v/release/flowcdhome/kestrel?style=for-the-badge&color=2ea44f)](https://github.com/flowcdhome/kestrel/releases)
[![License](https://img.shields.io/github/license/flowcdhome/kestrel?style=for-the-badge)](LICENSE)
![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)

</div>

---

## 💡 The idea

Classic username tools rely on a hand-written rule per site ("HTTP 404 means missing", "text X means missing"). Sites change, rules rot, and you get false positives and misses.

Kestrel does it differently:

1. **Baseline.** For each site it requests two random, certainly non-existent nicknames and records what "missing" looks like: status, redirect target, page title, content fingerprint.
2. **Differential check.** Your nickname is compared with that baseline. Different = profile exists. Same = missing.
3. **Confidence score.** Every hit gets 0-100 with reasons (e.g. `baseline is HTTP 404, profile is HTTP 200`, `nickname appears on the page`).
4. **Self-verification.** `kestrel verify` tests every site with a known real account and a random one, finds broken or false-positive sites and can disable them automatically.

Site-specific signatures are optional hints on top, not a requirement, so adding a site is just a URL.

## ✨ Features

- Async engine, per-host rate limit, retry, proxy and Tor support
- 600+ sites via `import-wmn` (downloaded to your machine from [WhatsMyName](https://github.com/WebBreacher/WhatsMyName)) plus a built-in core list
- Name variants: `--variants "john doe"` tries `johndoe`, `john.doe`, `jdoe`...
- Profile metadata (title, description) with `--details`
- Reports: terminal table, JSON, CSV, HTML
- Baseline cache (24 h), so repeated searches are much faster

## 🚀 Install

```bash
sudo pacman -S --needed git python python-pipx
git clone https://github.com/flowcdhome/kestrel.git
cd kestrel && ./install.sh
kestrel import-wmn           # 600+ sites (once)
kestrel verify --apply       # drop broken sites (once, repeat now and then)
kestrel somenick
```

Debian/Ubuntu: `sudo apt install git python3 pipx`.

## 📖 Usage

```bash
kestrel nick                          # search one nick
kestrel nick1 nick2                   # several
kestrel "john doe" --variants         # name variants
kestrel nick --details --html r.html  # profile info + report
kestrel nick --json r.json --csv r.csv
kestrel nick --cat coding             # one category
kestrel nick --tor                    # via Tor (socks5://127.0.0.1:9050)
kestrel nick --proxy socks5://127.0.0.1:1080
kestrel nick --min-confidence 70      # only strong hits
kestrel verify [--apply]              # test the site database
kestrel sites                         # what is enabled
```

## 🧩 Adding your own sites

Create `~/.config/kestrel/sites/mine.json`:

```json
[
  {
    "name": "MySite",
    "url": "https://mysite.example/u/{}",
    "cat": "social",
    "known": ["some_real_account"]
  }
]
```

Optional hints: `show_url`, `redirects` (false = do not follow), `exists_text`, `exists_status`, `missing_text`, `missing_status`. Then run `kestrel verify` to check it.

## ⚠️ Limits

- A found profile does **not** prove it belongs to the person you look for.
- Sites with captchas, bot protection or a VPN block show up as "unknown", not as a wrong answer.
- A new project: accuracy depends on the site list, run `kestrel verify` regularly.

## ⚖️ Responsible use

Use it for checking your own footprint, security research and lawful investigations. Do not use it for stalking or harassment. Respect site terms and the law.

## 🙏 Credits

Idea inspired by [Sherlock](https://github.com/sherlock-project/sherlock); no code is taken from it. Site list for `import-wmn`: [WhatsMyName](https://github.com/WebBreacher/WhatsMyName) (CC BY-SA 4.0), downloaded on your machine and not bundled here.

## 📄 License

MIT, see [LICENSE](LICENSE).
