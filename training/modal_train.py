"""Fine-tune Qwen3.5-4B with bf16 LoRA on Modal using Unsloth (Plan 7.2, decision D6).

What this does
- Reads data/train/sft_r1_train.jsonl and sft_r1_dev.jsonl (built by training/build_dataset.py)
  and checks their hashes against manifest_r1.json, so we train on exactly what the manifest says.
- Renders every example with the base model's own chat template, thinking off, the same way
  vLLM renders it when serving. The loss counts only the final answer: the system text, the
  few-shot turns and the document are masked, and so are CORD's unlabelled null fields.
- LoRA on attention and MLP layers only (q/k/v/o, gate/up/down). The linear-attention
  (GatedDeltaNet) projections are left alone, so vLLM bug #47639 cannot trigger.
- Saves the adapter to the docduel-adapters volume (/adapters/<name>), which the serving app
  mounts, and returns the loss log and a loss chart for reports/.

Run from the repo root:
  modal run training/modal_train.py --smoke   # 5 steps on a few examples: pipeline + speed
  modal run training/modal_train.py           # the real run (Gate 7 approved)
  modal run training/modal_train.py --round 2 # round 2 from the base model (Gate 8)
"""

import hashlib
import json
import pathlib
import time

import modal

MODEL_ID = "Qwen/Qwen3.5-4B"
MODEL_REVISION = "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"  # same weights as small-base
# Round 2 (Plan 8.7) trains from the base model again with the same settings; only the data changes.
GPU = "L40S"  # Owner choice 2026-09-28: 48 GB, $1.95/h, faster than L4
GPU_USD_PER_HOUR = 1.95

SEED = 2026
MAX_LEN = 4096  # prompt with few-shots is ~2k tokens; longer examples are dropped, not cut
LORA_R = 16
LORA_ALPHA = 32
LORA_TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
LEARNING_RATE = 2e-4
EPOCHS = 2
BATCH = 4
GRAD_ACCUM = 4  # 16 examples per optimiser step
EVAL_STEPS = 20
SAVE_STEPS = 20  # checkpoint to the volume; a cancelled run resumes from here

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("build-essential", "git")  # Triton compiles small kernels at start-up
    .uv_pip_install("unsloth", "unsloth_zoo", "flash-linear-attention", "matplotlib")
    .env({"HF_XET_HIGH_PERFORMANCE": "1"})
)
hf_cache = modal.Volume.from_name("docduel-hf-cache", create_if_missing=True)
adapters = modal.Volume.from_name("docduel-adapters", create_if_missing=True)
app = modal.App("docduel-train")


def encode(tok, ex: dict, max_len: int) -> dict | None:
    """Token ids plus labels; -100 marks tokens that do not count towards the loss."""
    prompt = tok.apply_chat_template(
        ex["messages"], tokenize=False, add_generation_prompt=True, enable_thinking=False
    )
    full = prompt + ex["answer"] + "<|im_end|>"
    enc = tok(full, add_special_tokens=False, return_offsets_mapping=True)
    ids = enc["input_ids"]
    if len(ids) > max_len:
        return None
    start = len(prompt)
    skip = [(start + a, start + b) for a, b in ex["mask_spans"]]
    labels = []
    for tid, (s, e) in zip(ids, enc["offset_mapping"], strict=True):
        counted = s >= start and not any(s < b and e > a for a, b in skip)
        labels.append(tid if counted else -100)
    return {"input_ids": ids, "attention_mask": [1] * len(ids), "labels": labels}


def loss_chart(history: list[dict], title: str) -> bytes:
    import io

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    tr = [(h["step"], h["loss"]) for h in history if "loss" in h]
    ev = [(h["step"], h["eval_loss"]) for h in history if "eval_loss" in h]
    fig, ax = plt.subplots(figsize=(7, 4), dpi=130)
    if tr:
        ax.plot(*zip(*tr, strict=True), color="#c0562e", label="training loss")
    if ev:
        ax.plot(*zip(*ev, strict=True), color="#2f6fb0", marker="o", label="validation loss (dev)")
    ax.set_xlabel("optimiser step")
    ax.set_ylabel("loss (answer tokens only)")
    ax.set_title(title)
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    return buf.getvalue()


@app.function(
    image=image,
    gpu=GPU,
    volumes={"/root/.cache/huggingface": hf_cache, "/adapters": adapters},
    timeout=3 * 60 * 60,
)
def train(train_rows: list[dict], dev_rows: list[dict], adapter: str, max_steps: int) -> dict:
    """Runs on the GPU. Returns only plain JSON text and PNG bytes: the PC has no torch, so any
    torch object in the result (or in an error) could not be unpacked locally."""
    import traceback

    try:
        log, png = _train(train_rows, dev_rows, adapter, max_steps)
    except Exception:
        raise RuntimeError("training failed on the GPU:\n" + traceback.format_exc()) from None
    return {"log_json": json.dumps(log, default=_plain), "png": png}


def _plain(o):
    """JSON fallback for torch/numpy numbers (e.g. grad_norm in the trainer's log history)."""
    return o.item() if hasattr(o, "item") else str(o)


def _train(train_rows: list[dict], dev_rows: list[dict], adapter: str, max_steps: int):
    import unsloth  # noqa: I001  (Unsloth must be imported before transformers)
    from unsloth import FastLanguageModel
    import peft
    import torch
    import transformers
    from transformers import Trainer, TrainerCallback, TrainingArguments, set_seed

    class StepTimer(TrainerCallback):
        """Seconds per optimiser step, to estimate the full run from the smoke run."""

        def __init__(self) -> None:
            self.times: list[float] = []
            self.last = 0.0

        def on_step_begin(self, *_, **__):
            self.last = time.time()

        def on_step_end(self, *_, **__):
            self.times.append(round(time.time() - self.last, 2))

    class CommitCheckpoints(TrainerCallback):
        """Push each checkpoint to the Modal volume so a cancelled run can resume."""

        def on_save(self, *_, **__):
            adapters.commit()

    t0 = time.time()
    set_seed(SEED)
    ckpt_dir = pathlib.Path("/adapters/_checkpoints") / adapter
    model, tok = FastLanguageModel.from_pretrained(
        model_name=MODEL_ID,
        revision=MODEL_REVISION,
        max_seq_length=MAX_LEN,
        load_in_4bit=False,
        load_in_16bit=True,
        full_finetuning=False,
    )
    text_tok = getattr(tok, "tokenizer", tok)  # Qwen3.5 is a vision model: a processor wraps it
    model = FastLanguageModel.get_peft_model(
        model,
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=0,
        target_modules=LORA_TARGETS,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=SEED,
    )

    def encode_all(rows: list[dict]) -> tuple[list[dict], list[str]]:
        out, dropped = [], []
        for ex in rows:
            enc = encode(text_tok, ex, MAX_LEN)
            if enc is None:
                dropped.append(ex["id"])
            else:
                out.append(enc)
        return out, dropped

    train_ds, train_dropped = encode_all(train_rows)
    dev_ds, dev_dropped = encode_all(dev_rows)
    first = train_ds[0]
    check = text_tok.decode([t for t in first["labels"] if t != -100])
    print("trained part of example 1:", check[:400])

    pad = text_tok.pad_token_id if text_tok.pad_token_id is not None else text_tok.eos_token_id

    def collate(batch: list[dict]) -> dict:
        n = max(len(b["input_ids"]) for b in batch)
        cols = (("input_ids", pad), ("attention_mask", 0), ("labels", -100))
        return {k: torch.tensor([b[k] + [f] * (n - len(b[k])) for b in batch]) for k, f in cols}

    args = TrainingArguments(
        output_dir=str(ckpt_dir),
        per_device_train_batch_size=BATCH,
        per_device_eval_batch_size=BATCH,
        gradient_accumulation_steps=GRAD_ACCUM,
        num_train_epochs=EPOCHS,
        max_steps=max_steps,
        learning_rate=LEARNING_RATE,
        warmup_steps=10,
        lr_scheduler_type="linear",
        optim="adamw_8bit",
        weight_decay=0.01,
        bf16=True,
        logging_steps=5 if max_steps < 0 else 1,
        eval_strategy="steps",
        eval_steps=EVAL_STEPS if max_steps < 0 else max_steps,
        save_strategy="steps" if max_steps < 0 else "no",
        save_steps=SAVE_STEPS,
        save_total_limit=1,
        report_to="none",
        seed=SEED,
        data_seed=SEED,
        remove_unused_columns=False,
    )
    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=dev_ds,
        data_collator=collate,
    )
    timer = StepTimer()
    trainer.add_callback(timer)
    trainer.add_callback(CommitCheckpoints())
    before = float(trainer.evaluate()["eval_loss"])
    t_train = time.time()
    adapters.reload()
    resume = max_steps < 0 and any(ckpt_dir.glob("checkpoint-*"))
    if resume:
        print("resuming from the last checkpoint in", ckpt_dir)
    result = trainer.train(resume_from_checkpoint=True if resume else None)
    train_seconds = time.time() - t_train
    final = float(trainer.evaluate()["eval_loss"])

    out = pathlib.Path("/adapters") / adapter
    model.save_pretrained(str(out))
    text_tok.save_pretrained(str(out))
    log = {
        "adapter": adapter,
        "base_model": MODEL_ID,
        "base_revision": MODEL_REVISION,
        "gpu": GPU,
        "settings": {
            "method": "bf16 LoRA (Unsloth)",
            "lora_r": LORA_R,
            "lora_alpha": LORA_ALPHA,
            "lora_targets": LORA_TARGETS,
            "learning_rate": LEARNING_RATE,
            "epochs": EPOCHS,
            "max_steps": max_steps,
            "batch": BATCH,
            "grad_accum": GRAD_ACCUM,
            "max_len": MAX_LEN,
            "seed": SEED,
            "loss": "answer tokens only; CORD vendor/date/number nulls masked",
        },
        "versions": {
            "unsloth": unsloth.__version__,
            "transformers": transformers.__version__,
            "peft": peft.__version__,
            "torch": torch.__version__,
        },
        "examples": {"train": len(train_ds), "dev": len(dev_ds)},
        "dropped_too_long": {"train": train_dropped, "dev": dev_dropped},
        "trained_text_example_1": check[:600],
        "eval_loss_before": round(before, 4),
        "eval_loss_after": round(final, 4),
        "train_loss": round(float(result.training_loss), 4),
        "optimizer_steps": result.global_step,
        "train_seconds": round(train_seconds),
        "total_seconds": round(time.time() - t0),
        "step_seconds": timer.times,
        "history": trainer.state.log_history,
    }
    log = json.loads(json.dumps(log, default=_plain))  # plain numbers only from here on
    (out / "training_log.json").write_text(json.dumps(log, indent=1))
    adapters.commit()
    png = loss_chart(log["history"], f"{adapter}: loss on answer tokens")
    (out / "training_loss.png").write_bytes(png)
    log["resumed_from_checkpoint"] = resume
    (out / "training_log.json").write_text(json.dumps(log, indent=1))
    adapters.commit()
    return log, png


def _load(path: pathlib.Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x]


@app.local_entrypoint()
def main(smoke: bool = False, round: int = 1) -> None:  # noqa: A002 (CLI flag name)
    repo = pathlib.Path(__file__).resolve().parents[1]
    data = repo / "data" / "train"
    ROUND, ADAPTER = f"r{round}", f"small-ft-r{round}"
    manifest = json.loads((data / f"manifest_{ROUND}.json").read_text(encoding="utf-8"))
    rows = {}
    for split, meta in manifest["files"].items():
        path = data / meta["name"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != meta["sha256"]:
            raise SystemExit(f"{path.name} does not match manifest_{ROUND}.json - rebuild it")
        rows[split] = _load(path)

    adapter, max_steps, name = ADAPTER, -1, f"training_{ROUND}"
    if smoke:  # a few examples of every source, 3 steps: proves the pipeline end to end

        def few(rs: list[dict], n: int) -> list[dict]:
            seen: dict[str, int] = {}
            out = []
            for r in rs:
                if seen.get(r["source"], 0) < n:
                    out.append(r)
                    seen[r["source"]] = seen.get(r["source"], 0) + 1
            return out

        rows = {"train": few(rows["train"], 32), "dev": few(rows["dev"], 4)}
        adapter, max_steps, name = f"{ADAPTER}-smoke", 5, f"training_{ROUND}_smoke"
    full_steps = -(
        -len(_load(data / manifest["files"]["train"]["name"])) * EPOCHS // (BATCH * GRAD_ACCUM)
    )

    res = train.remote(rows["train"], rows["dev"], adapter, max_steps)
    reports = repo / "reports"
    log = json.loads(res["log_json"])
    (reports / f"{name}_log.json").write_text(json.dumps(log, indent=1) + "\n", encoding="utf-8")
    (reports / f"{name}_loss.png").write_bytes(res["png"])
    print(
        f"adapter /adapters/{adapter}: {log['examples']['train']} train examples, "
        f"{log['optimizer_steps']} steps, {log['train_seconds']} s training, "
        f"dev loss {log['eval_loss_before']} -> {log['eval_loss_after']}, "
        f"dropped {len(log['dropped_too_long']['train'])} too long"
    )
    print(f"reports/{name}_log.json and reports/{name}_loss.png written")
    steady = sorted(log["step_seconds"][1:] or log["step_seconds"])  # step 1 includes compiling
    if smoke and steady:
        per_step = steady[len(steady) // 2]
        minutes = per_step * full_steps / 60
        print(
            f"steady speed {per_step:.1f} s per step -> full run about {full_steps} steps, "
            f"{minutes:.0f} min of training, about ${minutes / 60 * GPU_USD_PER_HOUR:.2f} "
            f"(plus ~5 min loading and checks)"
        )
