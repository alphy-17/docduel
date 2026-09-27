import type { ReactNode } from "react"

import { FADE } from "@/hooks/useTypewriter"

/**
 * Smooth typewriter: reveals several text blocks one after another. The next few characters
 * fade in rather than popping, and the full text is always laid out (invisible until reached)
 * so nothing jumps. Screen readers get the whole text at once.
 */
/** Renders one block, given how many characters of the whole sequence are visible. */
export function Typed({ text, offset, shown }: { text: string; offset: number; shown: number }): ReactNode {
  const local = shown - offset
  if (local >= text.length + FADE) return text
  if (local <= 0) return <span className="opacity-0">{text}</span>
  const solid = Math.max(0, Math.floor(local) - FADE)
  const edge = text.slice(solid, Math.min(text.length, Math.floor(local)))
  return (
    <>
      {text.slice(0, solid)}
      {[...edge].map((ch, i) => (
        <span key={i} style={{ opacity: (edge.length - i) / (edge.length + 1) }}>
          {ch}
        </span>
      ))}
      <span className="opacity-0">{text.slice(solid + edge.length)}</span>
    </>
  )
}
