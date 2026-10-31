"""Telegram: send-only. The same bot may serve other projects, so this never reads updates."""
import json
import urllib.parse
import urllib.request

import config


def enabled():
    return bool(config.TELEGRAM_TOKEN and config.TELEGRAM_CHAT_ID) and not config.DEMO


def send(text):
    if not enabled():
        print("[telegram disabled]\n" + text)
        return
    data = urllib.parse.urlencode({"chat_id": config.TELEGRAM_CHAT_ID, "text": text[:4000],
                                   "disable_web_page_preview": "true"}).encode()
    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
    with urllib.request.urlopen(url, data=data, timeout=30) as r:
        r.read()
