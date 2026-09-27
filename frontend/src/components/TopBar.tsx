import { Moon, Sun } from "lucide-react"
import { useEffect, useState } from "react"

function initialDark(): boolean {
  try {
    const saved = localStorage.getItem("docduel-theme")
    if (saved) return saved === "dark"
  } catch {
    // storage can be blocked; fall back to the system setting
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches
}

export function TopBar() {
  const [dark, setDark] = useState(initialDark)

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark)
    try {
      localStorage.setItem("docduel-theme", dark ? "dark" : "light")
    } catch {
      // ignore
    }
  }, [dark])

  return (
    <header className="drop relative z-10 mx-auto mt-5 max-w-[1240px] px-4 sm:px-5">
      <div className="surface flex h-14 items-center gap-6 rounded-full pr-2 pl-5">
        <a href="/" className="font-serif text-[21px] font-bold tracking-tight">
          Doc<span className="text-brand transition-colors duration-500">Duel</span>
        </a>
        <nav aria-label="Main" className="flex gap-1">
          <a href="/" aria-current="page" className="rounded-full bg-wash px-3.5 py-1.5 font-medium">
            Duel
          </a>
          <span className="hidden px-3.5 py-1.5 font-medium text-ink-3 sm:inline" title="Arrives in Phase 5">
            Benchmark
          </span>
        </nav>
        <button
          type="button"
          onClick={() => setDark((d) => !d)}
          aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
          aria-pressed={dark}
          className="ml-auto grid size-10 place-items-center rounded-full text-ink-2 transition-colors hover:bg-wash hover:text-foreground"
        >
          <span key={dark ? "moon" : "sun"} className="grid place-items-center animate-in spin-in-45 fade-in duration-500">
            {dark ? <Moon className="size-[19px]" /> : <Sun className="size-[19px]" />}
          </span>
        </button>
      </div>
    </header>
  )
}
