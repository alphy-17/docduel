import type { CSSProperties, ReactNode } from "react"
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion"

import timeline from "./timeline.json"

export const FPS = 30
export const C = {
  base: "#1d2633",
  wall: ["#2c4a6e", "#1f5c5a", "#6b4a79", "#b65f3f", "#d19a3c", "#264060"],
  card: "#efe8dc",
  cardSolid: "#f7f2e9",
  ink: "#1b1a17",
  ink2: "#57544c",
  light: "#f3eee4",
  dim: "rgba(243,238,228,0.72)",
  teal: "#5cc2bb",
  brand: "#1f6f6b",
  ours: "#c0562e",
  openai: "#3f86d0",
  green: "#2fa66a",
  red: "#e0533d",
  amber: "#e2a03f",
}
export const SERIF = "Lora, serif"
export const SANS = "Poppins, sans-serif"
export const MONO = "'IBM Plex Mono', monospace"

export type ClipId = (typeof timeline.clips)[number]["id"]
const CLIPS = Object.fromEntries(timeline.clips.map((c) => [c.id, c])) as Record<string, (typeof timeline.clips)[number]>
export const clip = (id: string) => CLIPS[id]
/** Frame at which a narration clip starts, plus an optional offset in seconds. */
export const at = (id: string, plus = 0) => Math.round((CLIPS[id].start + plus) * FPS)
/** Frame at which a given caption word is spoken (first word starting with `word`), plus an offset in seconds. */
export const atWord = (id: string, word: string, plus = 0) => {
  const c = CLIPS[id]
  const hit = c.words.find((x) => x.w.toLowerCase().startsWith(word.toLowerCase()))
  if (!hit) throw new Error(`"${word}" is not in the ${id} caption`)
  return Math.round((c.start + hit.t + plus) * FPS)
}
export const TOTAL_FRAMES = Math.round(timeline.total * FPS)

export function useLayout() {
  const { width, height } = useVideoConfig()
  const vertical = height > width
  return { vertical, u: vertical ? width / 1080 : height / 1080, width, height }
}

/** Springy 0..1 that starts at `from` (frames, relative to the scene). Bouncy by default. */
export function usePop(from: number, bouncy = true) {
  const f = useCurrentFrame()
  const { fps } = useVideoConfig()
  return spring({ frame: f - from, fps, config: bouncy ? { damping: 11, stiffness: 160, mass: 0.7 } : { damping: 200 } })
}

export function useRamp(from: number, to: number, ease = (x: number) => 1 - Math.pow(1 - x, 3)) {
  const f = useCurrentFrame()
  return ease(interpolate(f, [from, to], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }))
}

export const popStyle = (p: number, lift = 30): CSSProperties => ({
  opacity: Math.min(1, p * 1.6),
  transform: `translateY(${(1 - p) * lift}px) scale(${0.6 + 0.4 * p})`,
})

export function Kicker({ children, color = C.teal }: { children: ReactNode; color?: string }) {
  const { u } = useLayout()
  return (
    <div style={{ fontFamily: SANS, fontWeight: 600, fontSize: 26 * u, letterSpacing: 4 * u, textTransform: "uppercase", color }}>
      {children}
    </div>
  )
}

/** Headline that pops in word by word. */
export function Words({ text, from, size, color = C.light, stagger = 3, font = SERIF, weight = 700, center = true }: {
  text: string
  from: number
  size: number
  color?: string
  stagger?: number
  font?: string
  weight?: number
  center?: boolean
}) {
  const { u } = useLayout()
  const f = useCurrentFrame()
  const { fps } = useVideoConfig()
  return (
    <div
      style={{
        fontFamily: font,
        fontWeight: weight,
        fontSize: size * u,
        lineHeight: 1.08,
        color,
        display: "flex",
        flexWrap: "wrap",
        justifyContent: center ? "center" : "flex-start",
        gap: `0 ${size * 0.26 * u}px`,
      }}
    >
      {text.split(" ").map((w, i) => {
        const p = spring({ frame: f - from - i * stagger, fps, config: { damping: 12, stiffness: 170, mass: 0.6 } })
        return (
          <span key={i} style={{ display: "inline-block", opacity: Math.min(1, p * 1.8), transform: `translateY(${(1 - p) * 0.6 * size * u}px) rotate(${(1 - p) * -6}deg)` }}>
            {w}
          </span>
        )
      })}
    </div>
  )
}

export const Card = ({ children, style }: { children: ReactNode; style?: CSSProperties }) => (
  <div
    style={{
      background: C.card,
      borderRadius: 28,
      boxShadow: "0 0 0 1px rgba(255,255,255,0.35), 0 30px 70px rgba(0,0,0,0.4)",
      overflow: "hidden",
      ...style,
    }}
  >
    {children}
  </div>
)

/** Fades a whole scene out over its last frames. */
export function useSceneOut(duration: number, frames = 8) {
  const f = useCurrentFrame()
  return interpolate(f, [duration - frames, duration], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })
}
