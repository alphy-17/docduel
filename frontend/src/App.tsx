import { useEffect, useState } from "react"

type Health = {
  status: string
  live_mode_enabled: boolean
  models: Record<string, { model_id: string | null; status: string; key_present: boolean }>
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch("/api/health")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setHealth)
      .catch((e: Error) => setError(e.message))
  }, [])

  return (
    <main className="mx-auto max-w-2xl p-6 font-sans">
      <h1 className="text-3xl font-bold">DocDuel</h1>
      <p className="mt-1 text-sm opacity-70">Phase 0 skeleton</p>
      <div className="mt-6 rounded-lg border p-4">
        {error && <p className="font-medium text-red-600">backend unreachable: {error}</p>}
        {!error && !health && <p>checking backend…</p>}
        {health && (
          <>
            <p className="font-medium text-green-600">backend {health.status === "ok" ? "OK" : health.status}</p>
            <ul className="mt-3 space-y-1 text-sm">
              {Object.entries(health.models).map(([key, m]) => (
                <li key={key}>
                  <code>{key}</code> — {m.model_id ?? "not set"} · {m.status} · key{" "}
                  {m.key_present ? "present" : "missing"}
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </main>
  )
}
