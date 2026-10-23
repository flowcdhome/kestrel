<div align="center">

# 🦅 Kestrel

**Поиск ников, который сам учит, как выглядит «не найдено» на каждом сайте, и проверяет собственную базу.**

[🇬🇧 English](README.md) · 🇷🇺 Русский

[![Release](https://img.shields.io/github/v/release/flowcdhome/kestrel?style=for-the-badge&color=2ea44f)](https://github.com/flowcdhome/kestrel/releases)
[![License](https://img.shields.io/github/license/flowcdhome/kestrel?style=for-the-badge)](LICENSE)
![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)

</div>

---

## 💡 Идея

Обычные инструменты для поиска ников полагаются на ручное правило для каждого сайта («404 значит нет», «текст X значит нет»). Сайты меняются, правила устаревают, появляются ложные срабатывания и пропуски.

Kestrel работает иначе:

1. **Базовый образец.** Для каждого сайта он запрашивает два случайных заведомо несуществующих ника и запоминает, как выглядит «нет профиля»: статус, редирект, заголовок, отпечаток содержимого.
2. **Сравнение.** Твой ник сравнивается с этим образцом. Отличается: профиль есть. Совпадает: профиля нет.
3. **Оценка уверенности.** Каждая находка получает 0-100 и причины (например, `baseline is HTTP 404, profile is HTTP 200`, `nickname appears on the page`).
4. **Самопроверка.** `kestrel verify` проверяет каждый сайт на известном настоящем аккаунте и на случайном нике, находит сломанные сайты и ложные срабатывания и может сам их отключить.

Подписи конкретных сайтов это необязательные подсказки, а не требование: чтобы добавить сайт, достаточно URL.

## ✨ Возможности

- Асинхронный движок, лимит на хост, повторы, прокси и Tor
- 600+ сайтов через `import-wmn` (скачиваются на твой компьютер из [WhatsMyName](https://github.com/WebBreacher/WhatsMyName)) плюс встроенный основной список
- Варианты имени: `--variants "john doe"` пробует `johndoe`, `john.doe`, `jdoe`...
- Данные профиля (заголовок, описание) с `--details`
- Отчёты: таблица в терминале, JSON, CSV, HTML
- Кэш образцов на 24 часа: повторные поиски заметно быстрее

## 🚀 Установка

```bash
sudo pacman -S --needed git python python-pipx
git clone https://github.com/flowcdhome/kestrel.git
cd kestrel && ./install.sh
kestrel import-wmn           # 600+ сайтов (один раз)
kestrel verify --apply       # отключить сломанные сайты (один раз, потом время от времени)
kestrel somenick
```

Debian/Ubuntu: `sudo apt install git python3 pipx`.

## 📖 Использование

```bash
kestrel nick                          # один ник
kestrel nick1 nick2                   # несколько
kestrel "john doe" --variants         # варианты имени
kestrel nick --details --html r.html  # данные профилей + отчёт
kestrel nick --json r.json --csv r.csv
kestrel nick --cat coding             # одна категория
kestrel nick --tor                    # через Tor (socks5://127.0.0.1:9050)
kestrel nick --proxy socks5://127.0.0.1:1080
kestrel nick --min-confidence 70      # только уверенные находки
kestrel verify [--apply]              # проверить базу сайтов
kestrel sites                         # что включено
```

## 🧩 Свои сайты

Создай `~/.config/kestrel/sites/mine.json`:

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

Необязательные подсказки: `show_url`, `redirects` (false: не переходить по редиректам), `exists_text`, `exists_status`, `missing_text`, `missing_status`. Потом запусти `kestrel verify`, чтобы проверить сайт.

## ⚠️ Ограничения

- Найденный профиль **не доказывает**, что он принадлежит нужному человеку.
- Сайты с капчей, защитой от ботов или блокировкой VPN попадают в «unknown», а не дают неверный ответ.
- Проект новый: точность зависит от списка сайтов, запускай `kestrel verify` регулярно.

## ⚖️ Ответственное использование

Используй для проверки собственного следа, исследований безопасности и законных расследований. Не используй для преследования. Соблюдай правила сайтов и закон.

## 🙏 Благодарности

Идея вдохновлена [Sherlock](https://github.com/sherlock-project/sherlock); код оттуда не взят. Список сайтов для `import-wmn`: [WhatsMyName](https://github.com/WebBreacher/WhatsMyName) (CC BY-SA 4.0), скачивается на твой компьютер и не входит в репозиторий.

## 📄 Лицензия

MIT, см. [LICENSE](LICENSE).
