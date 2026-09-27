import { useEffect, useMemo, useState } from "react"

export const CPS = 90 // characters per second
export const FADE = 6 // characters in the soft leading edge

function reducedMotion(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches
}

/** How many characters of the whole sequence are visible right now (grows smoothly). */
export function useTypewriter(blocks: string[], startDelayMs = 350): number {
  const total = useMemo(() => blocks.reduce((n, b) => n + b.length, 0), [blocks])
  const [shown, setShown] = useState(() => (reducedMotion() ? total : 0))

  useEffect(() => {
    if (reducedMotion()) return
    let frame = 0
    const start = performance.now() + startDelayMs
    const tick = (now: number) => {
      const n = Math.max(0, ((now - start) / 1000) * CPS)
      setShown(Math.min(total + FADE, n))
      if (n < total + FADE) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [total, startDelayMs])

  return shown
}

