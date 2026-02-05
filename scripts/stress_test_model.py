#!/usr/bin/env python3
"""
Simple stress test for a model inference endpoint.

Usage examples:
  # Single baseline run against local Ollama API
  ./scripts/stress_test_model.py --url http://127.0.0.1:11434/api/generate --model gpt-oss:120b --prompt "Say hi" --baseline

  # Run 100 total requests with concurrency 10
  ./scripts/stress_test_model.py --url http://127.0.0.1:11434/api/generate --model gpt-oss:120b --prompt "Hello" --requests 100 --concurrency 10

Notes:
- The script defaults to calling Ollama's /api/generate endpoint (http://127.0.0.1:11434/api/generate).
- It does NOT integrate with the Open WebUI app; it's a standalone script that posts JSON {model, prompt, stream:false}.
- Use responsibly: high concurrency on large models can exhaust GPU/CPU/memory.
"""

import argparse
import json
import time
import requests
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional


def do_request(url: str, model: str, prompt: str, timeout: float, max_tokens: Optional[int] = None) -> dict:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }
    if max_tokens is not None:
        try:
            payload["options"] = {"max_tokens": int(max_tokens)}
        except Exception:
            payload["options"] = {"max_tokens": max_tokens}
    start = time.perf_counter()
    try:
        res = requests.post(url, json=payload, timeout=timeout)
        elapsed = time.perf_counter() - start
        return {
            "ok": res.status_code == 200,
            "status_code": res.status_code,
            "elapsed": elapsed,
            "size": len(res.content) if res.content is not None else 0,
            "error": None if res.status_code == 200 else f"HTTP {res.status_code}",
            "text_head": (res.text[:200] + "...") if res.text else "",
        }
    except Exception as e:
        elapsed = time.perf_counter() - start
        return {"ok": False, "status_code": None, "elapsed": elapsed, "size": 0, "error": str(e), "text_head": ""}


def baseline_run(url: str, model: str, prompt: str, timeout: float, max_tokens: Optional[int] = None, save_output: Optional[str] = None):
    print("Running single baseline inference to warm model / measure single-user latency...")
    r = do_request(url, model, prompt, timeout, max_tokens=max_tokens)
    if r["ok"]:
        print(f"Baseline success: {r['elapsed'] * 1000:.1f} ms, response size {r['size']} bytes")
        print("Response head:")
        print(r["text_head"])
        if save_output:
            try:
                with open(save_output, "wb") as fh:
                    fh.write(requests.post(url, json={"model": model, "prompt": prompt, "stream": False, **({"options": {"max_tokens": max_tokens}} if max_tokens else {})}).content)
                print(f"Saved sample response to {save_output}")
            except Exception as e:
                print(f"Failed to save output: {e}")
    else:
        print(f"Baseline failed: error={r['error']} elapsed={r['elapsed']:.2f}s")
    return r


def run_stress(url: str, model: str, prompt: str, concurrency: int, total_requests: int, timeout: float, max_tokens: Optional[int] = None):
    print(f"Running stress test: total={total_requests}, concurrency={concurrency}")
    latencies = []
    errors = 0
    status_codes = {}

    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futures = [ex.submit(do_request, url, model, prompt, timeout, max_tokens=max_tokens) for _ in range(total_requests)]
        start_all = time.perf_counter()
        for fut in as_completed(futures):
            r = fut.result()
            latencies.append(r["elapsed"])
            if not r["ok"]:
                errors += 1
            sc = r["status_code"]
            if sc not in status_codes:
                status_codes[sc] = 0
            status_codes[sc] += 1
        total_time = time.perf_counter() - start_all

    success = total_requests - errors
    throughput = success / total_time if total_time > 0 else 0

    lat_ms = [l * 1000 for l in latencies]
    summary = {
        "count": total_requests,
        "success": success,
        "errors": errors,
        "total_time_s": total_time,
        "throughput_rps": throughput,
        "latency_ms_min": min(lat_ms) if lat_ms else None,
        "latency_ms_p50": statistics.median(lat_ms) if lat_ms else None,
        "latency_ms_mean": statistics.mean(lat_ms) if lat_ms else None,
        "latency_ms_p90": percentile(lat_ms, 90) if lat_ms else None,
        "latency_ms_p95": percentile(lat_ms, 95) if lat_ms else None,
        "latency_ms_p99": percentile(lat_ms, 99) if lat_ms else None,
        "latency_ms_max": max(lat_ms) if lat_ms else None,
        "status_codes": status_codes,
    }
    return summary


def percentile(data, p):
    if not data:
        return None
    data = sorted(data)
    k = (len(data) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(data) - 1)
    if f == c:
        return data[int(k)]
    d0 = data[f] * (c - k)
    d1 = data[c] * (k - f)
    return d0 + d1

def main():
    parser = argparse.ArgumentParser(description="Stress test a model inference endpoint")
    parser.add_argument("--url", default="http://127.0.0.1:11434/api/generate", help="Full endpoint URL to POST to")
    parser.add_argument("--model", default="gpt-oss:120b", help="Model name (example: gpt-oss:120b)")
    parser.add_argument("--prompt", default="The quick brown fox jumps over the lazy dog", help="Prompt to send to model")
    parser.add_argument("--timeout", type=float, default=120.0, help="Request timeout in seconds")
    parser.add_argument("--baseline", action="store_true", help="Run a single baseline request and exit")
    parser.add_argument("--concurrency", type=int, default=5, help="Concurrency for stress test")
    parser.add_argument("--requests", type=int, default=20, help="Total number of requests to send in stress test")
    parser.add_argument("--max-tokens", type=int, default=None, help="If set, include options.max_tokens in payload to request longer generations")
    parser.add_argument("--save-output", type=str, default=None, help="Optional file to write a sample response body to")

    args = parser.parse_args()

    print("Stress Test Script\n")
    print(f"Endpoint: {args.url}\nModel: {args.model}\nPrompt: {args.prompt[:80]}{'...' if len(args.prompt)>80 else ''}\n")

    # Baseline run
    b = baseline_run(args.url, args.model, args.prompt, args.timeout, max_tokens=args.max_tokens, save_output=args.save_output)
    if args.baseline:
        return

    # Wait a moment after baseline to let model settle
    time.sleep(1.0)

    summary = run_stress(args.url, args.model, args.prompt, args.concurrency, args.requests, args.timeout, max_tokens=args.max_tokens)

    print("\nTest summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
