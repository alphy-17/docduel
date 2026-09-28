"""Phase 6 checks for the Modal vLLM server (tasks 6.3, 6.3a, 6.6 and the acceptance curls).

    uv run python scripts/check_serving.py            # auth, models list, extract + describe
    uv run python scripts/check_serving.py --md-only  # rebuild reports/serving.md, no calls
    uv run python scripts/check_serving.py --adapter NAME  # is a LoRA served? no report

Reads MODAL_VLLM_BASE_URL and MODAL_VLLM_API_KEY from backend/.env and never prints the key.
Writes reports/serving_small-base.json and reports/serving.md (rule R5).
"""

import argparse
import asyncio
import json
import statistics
import sys
import time
from dataclasses import replace
from datetime import UTC, datetime

import httpx
from dotenv import load_dotenv

from docduel.ingest.vision import prepare_for_model
from docduel.models.client import client_for
from docduel.models.registry import load_models
from docduel.runs.orchestrator import run_model
from docduel.runs.prompting import build_prompt
from docduel.settings import BACKEND_DIR, REPO_DIR

load_dotenv(BACKEND_DIR / ".env")
KEY = "small-base"
IDLE_S = 6 * 60  # a little longer than the 5-minute scale-down window
SAMPLE = (
    "BLUE FIG CAFE\n12 Smith St Fitzroy VIC\nTax invoice 00123\n03/04/2026\n"
    "Flat white 5.50\nBanana bread 6.00\nSubtotal 11.50\nGST 1.05\nTotal AUD 11.50\nEFTPOS"
)


async def noop(*_):
    return None


def env(name: str) -> str:
    import os

    value = os.getenv(name, "")
    if not value:
        sys.exit(f"{name} is not set in backend/.env")
    return value


def check_auth(base: str, token: str) -> dict:
    """Without a token Modal must refuse; with it /v1/models must list small-base."""
    no_key = httpx.get(f"{base}/models", timeout=30)
    start = time.perf_counter()
    while True:  # the first call may wake the GPU
        r = httpx.get(f"{base}/models", headers={"Authorization": f"Bearer {token}"}, timeout=600)
        if r.status_code == 200 or time.perf_counter() - start > 900:
            break
        time.sleep(5)
    names = [m["id"] for m in r.json().get("data", [])] if r.status_code == 200 else []
    return {
        "without_token_status": no_key.status_code,
        "with_token_status": r.status_code,
        "models": names,
        "wake_seconds": round(time.perf_counter() - start, 1),
        "pass": no_key.status_code in (401, 403) and KEY in names,
    }


async def one_extract(spec) -> dict:
    out = await run_model(spec, build_prompt("extract", text=SAMPLE), noop, client_for)
    return {
        "schema_valid": out.schema_valid,
        "error_code": out.error_code,
        "ttft_ms": out.ttft_ms and round(out.ttft_ms),
        "latency_ms": out.latency_ms and round(out.latency_ms),
        "output_tokens": out.output_tokens,
        "total": (out.parsed or {}).get("total"),
    }


async def one_describe(spec) -> dict:
    photo = (BACKEND_DIR / "tests" / "fixtures" / "receipt_photo.jpg").read_bytes()
    image = prepare_for_model(photo, "image")
    out = await run_model(
        spec, build_prompt("describe", image=(image, "image/jpeg")), noop, client_for
    )
    return {
        "ok": out.error_code is None and bool(out.raw_output.strip()),
        "error_code": out.error_code,
        "latency_ms": out.latency_ms and round(out.latency_ms),
        "input_tokens": out.input_tokens,
        "preview": out.raw_output[:160],
    }


CONFIGS = [  # earlier runs kept for comparison (Owner kept copies of each report)
    ("serving_small-base_eager.json", "eager mode, LoRA on"),
    ("serving_small-base_cudagraphs.json", "CUDA graphs, LoRA off"),
    ("serving_small-base.json", "CUDA graphs + MTP (current)"),
]


def write_md() -> None:
    """Build reports/serving.md from the saved JSON reports only (rule R5)."""
    rows, current = [], None
    for name, label in CONFIGS:
        path = REPO_DIR / "reports" / name
        if not path.exists():
            continue
        r = json.loads(path.read_text(encoding="utf-8"))
        current = r
        w = r["warm"]
        rows.append(
            f"| {label} | {w['ttft_ms_p50']} ms | {w['latency_ms_p50'] / 1000:.1f} s | "
            f"{w['latency_ms_max'] / 1000:.1f} s | {r['auth']['wake_seconds']:.0f} s |"
        )
    if current is None:
        sys.exit("no serving report yet")
    a = current["auth"]
    lines = [
        "# Serving: small-base on Modal",
        "",
        f"- Model: {current['model']} (Qwen/Qwen3.5-4B) on one {current['gpu']}, vLLM 0.30.0",
        f"- Auth: without token HTTP {a['without_token_status']}, with token HTTP "
        f"{a['with_token_status']}, models {a['models']}",
        f"- Structured output (extract JSON schema): {current['extract_first']['schema_valid']}",
        f"- Vision (describe): {current['describe']['ok']}, "
        f"{current['describe']['input_tokens']} input tokens",
        "",
        "| Server settings | First token p50 | Warm answer p50 | Warm max | Wake from sleep |",
        "|---|---|---|---|---|",
        *rows,
        "",
        "Warm = 5 extract calls on a small receipt after the GPU is awake. Wake from sleep = the "
        "first request of each run, from a sleeping GPU to a ready server (one sample each; the "
        "eager and graphs runs include first-time graph building).",
    ]
    cold = current.get("cold")
    if cold:
        lines.append(
            f"- Cold starts: {len(cold['wake_seconds'])} timed, median {cold['median_s']} s."
        )
    if current.get("cold_failed"):
        lines.append(
            f"- Cold starts over the wake limit: {len(current['cold_failed'])} "
            f"(gave up after {current['cold_failed']} s)."
        )
    (REPO_DIR / "reports" / "serving.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cold", type=int, default=0, help="cold starts to time (6 min apart)")
    ap.add_argument("--warm", type=int, default=5, help="warm extract calls to time")
    ap.add_argument("--md-only", action="store_true", help="rebuild serving.md, no model calls")
    ap.add_argument("--adapter", help="served LoRA name: check it is listed and answers valid JSON")
    args = ap.parse_args()
    if args.md_only:
        write_md()
        print("report: reports/serving.md")
        return

    base, token = env("MODAL_VLLM_BASE_URL").rstrip("/"), env("MODAL_VLLM_API_KEY")
    spec = load_models()[KEY]
    if args.adapter:
        auth = check_auth(base, token)
        print("served models:", auth["models"], f"(wake {auth['wake_seconds']} s)")
        if args.adapter not in auth["models"]:
            sys.exit(f"{args.adapter} is not served")
        print("extract:", await one_extract(replace(spec, model_id=args.adapter)))
        return
    report: dict = {
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "model": spec.model_id,
        "gpu": spec.gpu,
    }
    report["auth"] = check_auth(base, token)
    print("auth:", {k: v for k, v in report["auth"].items()})
    report["extract_first"] = await one_extract(spec)
    print("extract:", report["extract_first"])
    report["describe"] = await one_describe(spec)
    print("describe:", report["describe"])
    warm = [await one_extract(spec) for _ in range(args.warm)]
    report["warm"] = {
        "runs": len(warm),
        "all_valid": all(r["schema_valid"] for r in warm),
        "ttft_ms_p50": round(statistics.median(r["ttft_ms"] for r in warm)),
        "latency_ms_p50": round(statistics.median(r["latency_ms"] for r in warm)),
        "latency_ms_max": max(r["latency_ms"] for r in warm),
    }
    print("warm:", report["warm"])

    if args.cold:
        waits, failed = [], []
        for i in range(args.cold):
            print(f"cold start {i + 1}/{args.cold}: waiting {IDLE_S // 60} min for GPU sleep")
            await asyncio.sleep(IDLE_S)
            start = time.perf_counter()
            r = await one_extract(spec)
            took = round(time.perf_counter() - start, 1)
            if r["error_code"]:
                print(f"  FAILED after {took} s: {r['error_code']} (not counted)")
                failed.append(took)
                continue
            waits.append(took)
            print(f"  first answer after {took} s, valid {r['schema_valid']}")
        if waits:
            report["cold"] = {"wake_seconds": waits, "median_s": statistics.median(waits)}
        if failed:
            report["cold_failed"] = failed

    path = REPO_DIR / "reports" / "serving_small-base.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    write_md()
    print(f"report: reports/{path.name} and reports/serving.md")


if __name__ == "__main__":
    asyncio.run(main())
