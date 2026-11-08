"""Hızlı oylama yükü (HTTP): ardışık oy + her oydan sonra /votes/queue; gecikme ve kaynak raporu.

Çalışan bir backend'e karşı çalışır (örn. docker-compose.limits.yml ile 0.1 CPU / 512 MB).
Token yalnızca ortamdan (TINI_BENCH_TOKEN) ya da --token ile alınır ve çıktıya yazılmaz.
CLI: python -m app.jobs.rapid_vote_bench --base-url http://127.0.0.1:8000 [--votes 100]
     [--card-delay 1.0] [--pid PID | --container ADI]
"""
import argparse
import json
import math
import os
import subprocess
import sys
import time

import httpx


def percentile(values: list[float], p: float) -> float:
    """En yakın sıra yöntemi; boş listede 0."""
    if not values:
        return 0.0
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, math.ceil(p / 100 * len(ordered)) - 1))
    return ordered[k]


def summarize(latencies_ms: list[float], empty: int, server_errors: int, rss_mb: dict) -> dict:
    return {
        "queue_requests": len(latencies_ms),
        "p50_ms": round(percentile(latencies_ms, 50)),
        "p95_ms": round(percentile(latencies_ms, 95)),
        "max_ms": round(max(latencies_ms, default=0.0)),
        "empty_responses": empty,
        "server_errors_5xx": server_errors,
        "rss_mb": rss_mb,
    }


def read_rss_mb(pid: int | None = None, container: str | None = None) -> float | None:
    """Backend süreç RSS'i (MB). psutil → /proc → docker stats sırasıyla; yoksa None."""
    if pid is not None:
        try:
            import psutil

            return round(psutil.Process(pid).memory_info().rss / 2**20, 1)
        except ImportError:
            pass
        except Exception:  # noqa: BLE001
            return None
        try:
            with open(f"/proc/{pid}/status", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        return round(int(line.split()[1]) / 1024, 1)
        except OSError:
            return None
    if container:
        try:
            out = subprocess.run(
                ["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", container],
                capture_output=True, text=True, timeout=30, check=True,
            ).stdout.split("/")[0].strip()
        except (OSError, subprocess.SubprocessError):
            return None
        units = {"KiB": 1 / 1024, "MiB": 1.0, "GiB": 1024.0}
        for unit, mult in units.items():
            if out.endswith(unit):
                return round(float(out[: -len(unit)]) * mult, 1)
    return None


def run(base_url: str, token: str, votes: int, card_delay: float, vote_value: int,
        pid: int | None, container: str | None, timeout: float) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    latencies: list[float] = []
    empty = errors = 0
    rss: dict[str, float | None] = {"start": read_rss_mb(pid, container)}
    peak = rss["start"] or 0.0
    with httpx.Client(base_url=base_url, headers=headers, timeout=timeout) as c:
        for i in range(votes):
            t0 = time.perf_counter()
            try:
                r = c.get("/votes/queue")
            except httpx.HTTPError:
                errors += 1
                latencies.append((time.perf_counter() - t0) * 1000)
                time.sleep(card_delay)
                continue
            latencies.append((time.perf_counter() - t0) * 1000)
            if r.status_code >= 500:
                errors += 1
            items = r.json().get("items", []) if r.status_code == 200 else []
            if r.status_code == 200 and not items:
                empty += 1
            if items:
                v = c.post("/votes", json={"track": items[0]["track"], "vote": vote_value})
                if v.status_code >= 500:
                    errors += 1
            time.sleep(card_delay)
            if i % 10 == 9:
                peak = max(peak, read_rss_mb(pid, container) or 0.0)
    rss["end"] = read_rss_mb(pid, container)
    rss["peak"] = max(peak, rss["end"] or 0.0) or None
    return summarize(latencies, empty, errors, rss)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base-url", default=os.environ.get("TINI_BENCH_URL", "http://127.0.0.1:8000"))
    ap.add_argument("--token", default=os.environ.get("TINI_BENCH_TOKEN", ""))
    ap.add_argument("--votes", type=int, default=100)
    ap.add_argument("--card-delay", type=float, default=1.0, help="kart başına bekleme (sn)")
    ap.add_argument("--vote-value", type=int, default=4)
    ap.add_argument("--pid", type=int, default=None, help="backend süreç kimliği (RSS için)")
    ap.add_argument("--container", default=None, help="docker kapsayıcı adı (RSS için)")
    ap.add_argument("--timeout", type=float, default=60.0)
    args = ap.parse_args(argv)
    if not args.token:
        print("Token yok: TINI_BENCH_TOKEN ortam değişkenini ayarla.", file=sys.stderr)
        return 2
    result = run(args.base_url, args.token, args.votes, args.card_delay, args.vote_value,
                 args.pid, args.container, args.timeout)
    result = {"base_url": args.base_url, "votes": args.votes, "card_delay_s": args.card_delay,
              **result}
    print(json.dumps(result, ensure_ascii=False))
    print(
        f"özet: p50={result['p50_ms']} ms  p95={result['p95_ms']} ms  maks={result['max_ms']} ms  "
        f"boş={result['empty_responses']}  5xx={result['server_errors_5xx']}  "
        f"RSS(tepe)={result['rss_mb'].get('peak')} MB",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
