import { Moon, Sun } from "lucide-react"
import { useEffect, useState } from "react"

import { DEMO } from "@/lib/api"
import { cn } from "@/lib/utils"

function initialDark(): boolean {
  try {
    const saved = localStorage.getItem("docduel-theme")
    if (saved) return saved === "dark"
  } catch {
    // storage can be blocked; fall back to the system setting
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches
}

const PAGES = [
  { path: "/", label: "Duel" },
  { path: "/benchmark", label: "Benchmark" },
  // The Corrections page is a local tool for the Owner; the public site does not show it.
  ...(DEMO ? [] : [{ path: "/corrections", label: "Corrections" }]),
  { path: "/about", label: "About" },
]

export function TopBar({ path, onNavigate }: { path: string; onNavigate: (to: string) => void }) {
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
      <div className="surface flex h-14 items-center gap-2 rounded-full pr-2 pl-4 sm:gap-6 sm:pl-5">
        <a
          href="/"
          onClick={(e) => {
            e.preventDefault()
            onNavigate("/")
          }}
          className="font-serif text-[17px] font-bold tracking-tight sm:text-[21px]"
        >
          Doc<span className="text-brand transition-colors duration-500">Duel</span>
        </a>
        <nav aria-label="Main" className="flex min-w-0 gap-0.5 sm:gap-1">
          {PAGES.map((p) => (
            <a
              key={p.path}
              href={p.path}
              aria-current={path === p.path ? "page" : undefined}
              onClick={(e) => {
                if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return
                e.preventDefault()
                onNavigate(p.path)
              }}
              className={cn(
                "rounded-full px-1.5 py-1.5 text-[13px] font-medium transition-colors sm:px-3.5 sm:text-[14px]",
                path === p.path ? "bg-wash" : "text-ink-2 hover:text-foreground",
              )}
            >
              {p.label}
            </a>
          ))}
        </nav>
        <button
          type="button"
          onClick={() => setDark((d) => !d)}
          aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
          aria-pressed={dark}
          className="ml-auto grid size-9 shrink-0 sm:size-10 place-items-center rounded-full text-ink-2 transition-colors hover:bg-wash hover:text-foreground"
        >
          <span
            key={dark ? "moon" : "sun"}
            className="grid place-items-center animate-in spin-in-45 fade-in duration-500"
          >
            {dark ? <Moon className="size-[19px]" /> : <Sun className="size-[19px]" />}
          </span>
        </button>
      </div>
    </header>
  )
}
