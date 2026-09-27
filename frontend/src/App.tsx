import { useEffect, useState } from "react"

import { BenchmarkPage } from "@/components/benchmark/BenchmarkPage"
import { ModelPanel } from "@/components/duel/ModelPanel"
import { StatsTable, Verdict } from "@/components/duel/Results"
import { SourceCard } from "@/components/duel/SourceCard"
import { TopBar } from "@/components/TopBar"
import { Wallpaper } from "@/components/Wallpaper"
import { useDuel, type PanelState } from "@/hooks/useDuel"
import { usePath } from "@/hooks/usePath"
import { getHealth } from "@/lib/api"
import type { HealthModel } from "@/lib/types"

// Before a run, show the two panels empty so the layout never jumps (Owner wireframe).
const IDLE: PanelState[] = [
  { key: "small-base", status: "idle", text: "", startedAt: 0 },
  { key: "openai", status: "idle", text: "", startedAt: 0 },
]

export default function App() {
  const duel = useDuel()
  const [path, go] = usePath()
  const [models, setModels] = useState<Record<string, HealthModel>>({})
  const [backendDown, setBackendDown] = useState(false)

  useEffect(() => {
    getHealth()
      .then(setModels)
      .catch(() => setBackendDown(true))
  }, [])

  const running = duel.panels.length > 0
  const panels = running ? duel.panels : IDLE
  const placeholders = running ? duel.placeholders : []
  const task = duel.runTask ?? duel.task
  const [left, right] = panels

  return (
    <>
      <Wallpaper />
      <TopBar path={path} onNavigate={go} />
      <main className="mx-auto flex max-w-[1240px] flex-col gap-5 px-4 pt-7 pb-14 sm:px-5">
        {path === "/benchmark" ? (
          <BenchmarkPage />
        ) : (
          <>
            <SourceCard
              phase={duel.phase}
              file={duel.file}
              doc={duel.doc}
              task={duel.task}
              instructions={duel.instructions}
              notice={backendDown ? "Can't reach the backend. Start it with uvicorn on port 8000." : duel.notice}
              onFile={duel.selectFile}
              onClear={duel.clear}
              onTask={duel.setTask}
              onInstructions={duel.setInstructions}
              onRun={duel.run}
            />

            <div className="grid gap-5 md:grid-cols-2">
              {panels.map((p, i) => (
                <ModelPanel
                  key={p.key}
                  delay={160 + i * 80}
                  panel={p}
                  other={p === left ? right : left}
                  task={task}
                  placeholder={placeholders.includes(p.key)}
                  modelId={models[p.key]?.model_id}
                  rowLabels={duel.rowLabels}
                  page={duel.page}
                  onPage={duel.setPage}
                  truth={running ? duel.truth?.results[p.key] : undefined}
                />
              ))}
            </div>

            <StatsTable panels={panels} />
            <Verdict task={running ? task : null} panels={running ? panels : []} truth={running ? duel.truth : null} />
          </>
        )}
      </main>
    </>
  )
}
