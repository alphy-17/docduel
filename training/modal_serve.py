"""Serve Qwen3.5-4B with vLLM on Modal behind an OpenAI-compatible API (Plan Phase 6).

What this does
- Runs `vllm serve` on one L4 GPU inside a Modal container.
- Model weights and vLLM's compile cache live on Modal Volumes, so they download once.
- Every request must carry a Modal proxy auth token ("Authorization: Bearer ID.SECRET").
  Modal checks it at its front door, so strangers can't reach any vLLM route (vLLM's own
  --api-key leaves some routes like /invocations open) and can't wake the GPU.
- Scales to zero after 5 idle minutes; at most one GPU container ever runs (cost cap).
- Keeps the vision encoder (the describe task sends images), thinking off by default.
- CUDA graphs on and MTP speculative decoding (Qwen's built-in draft head) for speed.
- LoRA serving is off until Phase 7/8 adapters exist.

Deploy:  modal deploy training/modal_serve.py
Check:   uv run python scripts/check_serving.py   (from backend/, uses the token in .env)
"""

import json
import subprocess

import modal

VLLM_VERSION = "0.30.0"  # Owner choice 2026-09-27 (latest)
MODEL_ID = "Qwen/Qwen3.5-4B"
MODEL_REVISION = "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"  # pinned: same weights every run
SERVED_NAMES = ["small-base", MODEL_ID]  # first name is what /v1/models reports

GPU = "L4"  # Owner choice: 24 GB, $0.80/h
SCALEDOWN_SECONDS = 5 * 60  # Owner choice: sleep after 5 idle minutes
MAX_MODEL_LEN = 16384  # our prompts are ~2k tokens; a 1536 px image adds a few thousand
FAST_BOOT = False  # CUDA graphs on: much faster answers; graphs cached on the vllm volume
MTP_TOKENS = 1  # speculative decoding with Qwen's own draft head: same answers, faster
ENABLE_LORA = False  # on in Phase 7 with adapters (target whole layer groups: vLLM bug #47639)
MAX_LORA_RANK = 32
PORT = 8000
MINUTES = 60

image = (
    modal.Image.from_registry("nvidia/cuda:12.9.0-devel-ubuntu22.04", add_python="3.12")
    .entrypoint([])
    .uv_pip_install(f"vllm=={VLLM_VERSION}")
    .env({"HF_XET_HIGH_PERFORMANCE": "1"})
)

hf_cache = modal.Volume.from_name("docduel-hf-cache", create_if_missing=True)
vllm_cache = modal.Volume.from_name("docduel-vllm-cache", create_if_missing=True)
adapters = modal.Volume.from_name("docduel-adapters", create_if_missing=True)

app = modal.App("docduel-vllm")


def serve_command() -> list[str]:
    cmd = [
        "vllm",
        "serve",
        MODEL_ID,
        "--revision",
        MODEL_REVISION,
        "--served-model-name",
        *SERVED_NAMES,
        "--host",
        "0.0.0.0",
        "--port",
        str(PORT),
        "--max-model-len",
        str(MAX_MODEL_LEN),
        "--gpu-memory-utilization",
        "0.90",
        # One image per request for describe; no video.
        "--limit-mm-per-prompt",
        json.dumps({"image": 1, "video": 0}),
        # Thinking off unless a request turns it on (Plan 3: same settings both sides).
        "--reasoning-parser",
        "qwen3",
        "--default-chat-template-kwargs",
        json.dumps({"enable_thinking": False}),
        "--enforce-eager" if FAST_BOOT else "--no-enforce-eager",
        "--uvicorn-log-level",
        "warning",
    ]
    if MTP_TOKENS:
        cmd += [
            "--speculative-config",
            json.dumps({"method": "mtp", "num_speculative_tokens": MTP_TOKENS}),
        ]
    if ENABLE_LORA:
        cmd += ["--enable-lora", "--max-lora-rank", str(MAX_LORA_RANK), "--max-loras", "2"]
    return cmd


@app.server(
    image=image,
    gpu=GPU,
    volumes={
        "/root/.cache/huggingface": hf_cache,
        "/root/.cache/vllm": vllm_cache,
        "/adapters": adapters,
    },
    port=PORT,
    startup_timeout=15 * MINUTES,  # first boot downloads ~9 GB of weights
    scaledown_window=SCALEDOWN_SECONDS,
    max_containers=1,  # never more than one GPU at a time
    target_concurrency=8,
    unauthenticated=False,  # Modal proxy auth token required on every request
)
class Server:
    @modal.enter()
    def start(self) -> None:
        print("starting:", " ".join(serve_command()))
        self.process = subprocess.Popen(serve_command())

    @modal.exit()
    def stop(self) -> None:
        self.process.terminate()
