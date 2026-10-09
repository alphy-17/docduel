// Plan 9.9: what DocDuel is, how it works and what it does not do. No numbers here on purpose:
// every score lives on the Benchmark page, which reads them from the report files (rule R5).

const anim = (d: number) => ({ ["--d" as string]: `${d}ms` })

const STEPS = [
  {
    title: "Read the document",
    body: "PDFs with a text layer are read directly. Scans and photos go through Azure Document Intelligence for the text. CSV files are parsed as tables.",
  },
  {
    title: "Ask both models at once",
    body: "The same prompt and the same JSON schema go to OpenAI gpt-6-luna and to our model, Qwen3.5-4B with a LoRA adapter trained for this job, served with vLLM on one rented L4 GPU. Both answers stream back as they are written.",
  },
  {
    title: "Check the answers",
    body: "On documents from the frozen test set, every field is compared with a hand-checked answer key. On anything else the two models are only compared with each other, because we do not know the right answer.",
  },
]

const LIMITS = [
  "OpenAI is more accurate on every headline metric, and cheaper when documents arrive one at a time.",
  "Categorising bank rows works well on the training-like files and noticeably worse on new merchants.",
  "Unusual layouts trip the model up until it has seen corrected examples of them.",
  "Documents are limited to 3 pages, because that is what the model was trained and measured on.",
  "The GPU sleeps when idle, so the first live run after a quiet spell waits a few minutes for it to start.",
]

export function AboutPage({ onNavigate }: { onNavigate: (to: string) => void }) {
  const link = (to: string, label: string) => (
    <a
      href={to}
      onClick={(e) => {
        e.preventDefault()
        onNavigate(to)
      }}
      className="font-medium underline underline-offset-4"
    >
      {label}
    </a>
  )

  return (
    <>
      <section className="surface rise rounded-xl px-5 py-5 sm:px-7 sm:py-6" style={anim(0)}>
        <h1 className="font-serif text-[30px] leading-tight font-bold sm:text-[34px]">About DocDuel</h1>
        <p className="mt-3 max-w-[760px] text-[15px] text-ink-2">
          DocDuel asks whether a small open model, fine-tuned on receipts and invoices, can read them as well as a
          frontier API, and what each one costs to run. The {link("/", "Duel")} shows both models on the same document
          side by side. The {link("/benchmark", "Benchmark")} shows how they did on a frozen test set, including where
          our model loses.
        </p>
      </section>

      <section className="surface rise rounded-xl px-5 py-5 sm:px-7" style={anim(80)}>
        <h2 className="font-serif text-[19px] font-semibold">How a run works</h2>
        <ol className="mt-4 grid gap-4 md:grid-cols-3">
          {STEPS.map((s, i) => (
            <li key={s.title} className="inner rounded-lg border border-line-2 p-4">
              <span className="num grid size-6 place-items-center rounded-full bg-wash text-[12px] text-ink-2">
                {i + 1}
              </span>
              <h3 className="mt-2 font-medium">{s.title}</h3>
              <p className="mt-1 text-[14px] text-ink-2">{s.body}</p>
            </li>
          ))}
        </ol>
      </section>

      <div className="grid gap-5 md:grid-cols-2">
        <section className="surface rise rounded-xl px-5 py-5 sm:px-7" style={anim(160)}>
          <h2 className="font-serif text-[19px] font-semibold">How the small model learned</h2>
          <p className="mt-2 text-[14px] text-ink-2">
            Round 1 trained a LoRA adapter on public CORD receipts and synthetic invoices and bank files, using only
            true answers, never another model's output. Round 2 added hard invoices in a layout the model had not seen:
            the model filled each one in, a person checked and corrected it, and the corrections became new training
            data. The model shown in the Duel is the round with the best score on the development set; the test set is
            never used to choose.
          </p>
        </section>

        <section className="surface rise rounded-xl px-5 py-5 sm:px-7" style={anim(200)}>
          <h2 className="font-serif text-[19px] font-semibold">What it does not do well</h2>
          <ul className="mt-2 space-y-1.5 text-[14px] text-ink-2">
            {LIMITS.map((l) => (
              <li key={l} className="flex gap-2">
                <span aria-hidden="true" className="mt-[9px] size-1 shrink-0 rounded-full bg-ink-3" />
                {l}
              </li>
            ))}
          </ul>
        </section>
      </div>

      <section className="surface rise rounded-xl px-5 py-5 sm:px-7" style={anim(240)}>
        <h2 className="font-serif text-[19px] font-semibold">Replays and privacy</h2>
        <p className="mt-2 max-w-[860px] text-[14px] text-ink-2">
          The samples on this site play back real runs that were recorded with their original timing, so they work
          instantly and cost nothing. Running your own file uses the paid models and needs an access code. Uploaded
          files are not stored; images are kept in memory only while a run lasts.
        </p>
        <p className="mt-3 text-[14px] text-ink-2">
          Built by Alphy Baby.{" "}
          <a
            href="https://github.com/alphy-17/docduel"
            className="font-medium underline underline-offset-4"
            target="_blank"
            rel="noreferrer"
          >
            Source code on GitHub
          </a>
          .
        </p>
      </section>
    </>
  )
}
