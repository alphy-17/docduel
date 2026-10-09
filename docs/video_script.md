# DocDuel demo video script (about 2.5 minutes)

Record the screen at 1080p in a browser window about 1300 px wide, light theme. Read the numbers from the README results block on the day you record, so the video always matches the reports.

| # | Time | On screen | Say |
|---|---|---|---|
| 1 | 0:00 | Duel page, intro text visible | "This is DocDuel. It asks one question: can a small open model that I fine-tuned read receipts and invoices as well as OpenAI, and what does each one cost?" |
| 2 | 0:12 | Click the **Tax invoice** sample, then **Play the recorded run** | "Both models get the same document and the same prompt at the same moment. On the left is Qwen3.5-4B with a LoRA adapter I trained; on the right is OpenAI's gpt-6-luna. On the public site these are recordings of real runs, so they play instantly and cost nothing." |
| 3 | 0:35 | Scroll to the Analytics and Summary cards | "Underneath I get time, tokens and cost for each model, and where their answers agree." |
| 4 | 0:45 | Click **Dense invoice**, play it, point at the date field | "This one is a layout the model never saw, with American month and day dates. Round 1 gets the date wrong here. That is the weakness the second training round targets." |
| 5 | 1:00 | Benchmark page, headline table | "The Benchmark is a frozen test set the model never trained on, scored field by field with confidence ranges. Our model reaches [field accuracy as a share of OpenAI's, from the README] of OpenAI's field accuracy. OpenAI is still ahead on every metric, and the page says so." |
| 6 | 1:20 | Improvement over rounds chart | "Round 2 is the human-in-the-loop part. The model pre-filled 40 hard invoices, I corrected them by hand, and those corrections became training data. On held-out invoices of that layout, perfect documents went from [round 1] to [round 2]. It cost a little accuracy on everyday receipts, so I picked the headline model on the dev set, never on the test set." |
| 7 | 1:45 | README, cost rows and throughput table | "Cost is the honest catch. OpenAI bills per token and is very cheap. My model bills per GPU second, so one document at a time it is more expensive. [Say what the throughput table shows at higher volume.]" |
| 8 | 2:05 | About page or architecture diagram in the README | "Under the hood: a FastAPI backend in Docker on Azure Container Apps, the model served by vLLM on a Modal GPU that sleeps when idle, and a React front end on Vercel. Every number on the site and in the README is generated from report files." |
| 9 | 2:20 | GitHub repo page | "The code, the training scripts and every report are on GitHub. Thanks for watching." |

## Before recording

- Open each sample once so the pages are cached and nothing loads on camera.
- Do not show the live-mode access code, the Azure portal, `.env` or any terminal with keys.
- Keep the browser zoom at 100% so the tables are readable.
