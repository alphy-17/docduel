# Serving: small-base on Modal

- Model: small-base (Qwen/Qwen3.5-4B) on one L4, vLLM 0.30.0
- Auth: without token HTTP 401, with token HTTP 200, models ['small-base', 'Qwen/Qwen3.5-4B']
- Structured output (extract JSON schema): True
- Vision (describe): True, 792 input tokens

| Server settings | First token p50 | Warm answer p50 | Warm max | Wake from sleep |
|---|---|---|---|---|
| eager mode, LoRA on | 1005 ms | 10.2 s | 13.3 s | 286 s |
| CUDA graphs, LoRA off | 857 ms | 6.5 s | 8.4 s | 457 s |
| CUDA graphs + MTP (current) | 920 ms | 4.3 s | 5.6 s | 314 s |

Warm = 5 extract calls on a small receipt after the GPU is awake. Wake from sleep = the first request of each run, from a sleeping GPU to a ready server (one sample each; the eager and graphs runs include first-time graph building).
