"""Faz 0 dogrulama betikleri icin ortak yardimcilar. Uretim kodu degildir; stdlib disinda bagimlilik yok."""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)


def load_env():
    """Repo kokundeki .env dosyasini os.environ'a yukler (varsa)."""
    p = ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def need(name):
    v = os.environ.get(name)
    if not v:
        raise SystemExit(f"Eksik ortam degiskeni: {name} (.env icine ekle)")
    return v


def http(method, url, headers=None, params=None, body=None, form=None, retries=4):
    """(status, json_or_text) doner. 429'da Retry-After / ustel geri cekilme uygular."""
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    data = None
    hdrs = {"User-Agent": "tini-spike/0.1 (mustafabkr42@outlook.com)", **(headers or {})}
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        hdrs["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body).encode()
        hdrs["Content-Type"] = "application/json"
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, _parse(r.read())
        except urllib.error.HTTPError as e:
            payload = _parse(e.read())
            if e.code == 429 and attempt < retries:
                wait = int(e.headers.get("Retry-After", 2 ** (attempt + 1)))
                time.sleep(min(wait, 60))
                continue
            return e.code, payload
        except urllib.error.URLError as e:
            if attempt == retries:
                return 0, str(e)
            time.sleep(2 ** attempt)
    return 0, "retries exhausted"


def _parse(raw):
    text = raw.decode("utf8", "replace")
    try:
        return json.loads(text)
    except ValueError:
        return text[:500]
