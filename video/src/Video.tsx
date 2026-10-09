import type { ComponentType } from "react"
import { lightLeak } from "@remotion/effects/light-leak"
import { AbsoluteFill, Audio, interpolate, Sequence, Solid, staticFile, useCurrentFrame, useVideoConfig } from "remotion"

import { Cost, Data, End, Hook, Live, Loop, Race, Result, type SceneProps, Train } from "./Scenes"
import { at, atWord, C, FPS, MONO, SANS, TOTAL_FRAMES, useLayout } from "./kit"
import timeline from "./timeline.json"

// DocDuel promo, 60 s. Narration clips (public/vo) drive the timing; every number comes from
// data.json, generated from reports/*.json. Voice by ElevenLabs (make_voice.mjs); music and sound effects
// are synthesised by make_audio.py.

const LEAD = 6 // scenes start 0.2 s before their first line
const SCENES: [ComponentType<SceneProps>, string | null][] = [
  [Hook, null],
  [Race, "race"],
  [Data, "data"],
  [Train, "train"],
  [Result, "result"],
  [Loop, "layout"],
  [Cost, "cheaper"],
  [Live, "live"],
  [End, "name"],
]

// [sound, clip id, word in that caption (or null for the line start), offset in seconds, volume]
// Every sound is synthesised by make_audio.py and lands on the word it illustrates.
const SFX: [string, string, string | null, number, number?][] = [
  ["riser", "built", null, -1.5, 0.35],
  ["impact", "built", "DocDuel", 0, 0.6],
  ["whoosh", "race", null, -0.15, 0.4],
  ["typing", "race", "Same", 0.2, 0.3],
  ["ding", "race", "head", 0.3, 0.35],
  ["whoosh", "data", null, -0.15, 0.4],
  ["paper", "data", "800", -0.25, 0.4],
  ["pop", "data", "800", -0.1, 0.45],
  ["paper", "data", "500", -0.25, 0.35],
  ["pop", "data", "500", -0.1, 0.45],
  ["lock", "data", "locked", 0, 0.6],
  ["stamp", "never", "never", 0, 0.75],
  ["whoosh", "train", null, -0.15, 0.4],
  ["hum", "train", "training", 0, 0.3],
  ["blips", "qwen", "Qwen", 0.2, 0.18],
  ["pop", "qwen", "Qwen", -0.1, 0.45],
  ["pop", "qwen", "open", -0.1, 0.45],
  ["pop", "qwen", "rented", -0.1, 0.45],
  ["ding", "forty", "39", -0.05, 0.4],
  ["ding", "forty", "About", -0.05, 0.4],
  ["riser", "result", null, -0.3, 0.5],
  ["impact", "acc", null, 0, 0.6],
  ["whoosh", "layout", null, -0.15, 0.4],
  ["scan", "layout", "layout", -0.2, 0.4],
  ["error", "layout", "tripped", -0.05, 0.35],
  ["typing", "layout", "fixed", 0, 0.28],
  ...Array.from({ length: 10 }, (_, i) => ["tick", "layout", "fixed", 0.1 + i * 0.15, 0.25] as [string, string, string, number, number]),
  ["success", "perfect", "70%", 0, 0.45],
  ["whoosh", "cheaper", null, -0.15, 0.4],
  ["impact", "one", "No", 0, 0.45],
  ["chaching", "sixteen", "beats", 0, 0.45],
  ["whoosh", "live", null, -0.15, 0.4],
  ["chime", "live", "live", 0, 0.4],
  ["pop", "live", "React", -0.1, 0.45],
  ["pop", "live", "API", -0.1, 0.45],
  ["pop", "live", "model", -0.1, 0.45],
  ["impact", "name", null, 0, 0.6],
  ["pop", "try", null, 0.2, 0.45],
]

function Wallpaper() {
  const f = useCurrentFrame()
  const pulse = 1 + 0.012 * Math.max(0, Math.cos(((f / FPS) * 2 * Math.PI * 112) / 60))
  const d = (i: number) => `translate(${Math.sin(f / (40 + i * 6)) * 34}px, ${Math.cos(f / (46 + i * 5)) * 24}px) scale(${pulse})`
  const paths = [
    "M-80 -60h720c-40 140-160 250-330 270S70 260-80 330z",
    "M-80 560c170-80 360-70 520 10s330 150 520 110 330-150 560-120v440H-80z",
    "M1520 -40v420c-150 30-290-10-390-110S980 80 1000-40z",
    "M860 980c20-150 160-260 330-260s290 110 330 260z",
    "M-60 760c150-50 300-30 420 40s150 180 80 230H-60z",
    "M520 330c90-70 240-80 330-10s80 190-20 240-250 40-320-40-80-130 10-190z",
  ]
  return (
    <AbsoluteFill style={{ background: C.base }}>
      <svg width="100%" height="100%" viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice">
        {paths.map((p, i) => (
          <path key={i} d={p} fill={C.wall[i]} style={{ transform: d(i), transformOrigin: "720px 450px" }} />
        ))}
      </svg>
      <AbsoluteFill style={{ background: "rgba(16,22,30,0.38)" }} />
    </AbsoluteFill>
  )
}

/** Subtitles: the current line, with each word lighting up as it is spoken. */
function Captions() {
  const f = useCurrentFrame()
  const { u, vertical } = useLayout()
  const t = f / FPS
  const c = timeline.clips.find((x) => t >= x.start - 0.05 && t <= x.start + x.dur + 0.25)
  if (!c) return null
  const local = t - c.start
  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: (vertical ? 150 : 46) * u }}>
      <div
        style={{
          maxWidth: (vertical ? 940 : 1500) * u,
          textAlign: "center",
          background: "rgba(10,14,20,0.72)",
          borderRadius: 18 * u,
          padding: `${12 * u}px ${24 * u}px`,
          fontFamily: SANS,
          fontWeight: 600,
          fontSize: (vertical ? 40 : 34) * u,
          lineHeight: 1.35,
        }}
      >
        {c.words.map(({ w, t: wt }, i) => (
          <span key={i} style={{ color: local >= wt - 0.03 ? C.light : "rgba(243,238,228,0.42)" }}>
            {w}
            {i < c.words.length - 1 ? " " : ""}
          </span>
        ))}
      </div>
    </AbsoluteFill>
  )
}

/** Warm light leak flashed over a big moment (from @remotion/effects). */
function LightLeak({ seed, hueShift = 0 }: { seed: number; hueShift?: number }) {
  const frame = useCurrentFrame()
  const { durationInFrames, height, width } = useVideoConfig()
  return (
    <AbsoluteFill style={{ mixBlendMode: "screen", opacity: 0.55 }}>
      <Solid
        width={width}
        height={height}
        color="black"
        effects={[
          lightLeak({
            seed,
            hueShift,
            progress: interpolate(frame, [0, durationInFrames - 1], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
          }),
        ]}
      />
    </AbsoluteFill>
  )
}

const LEAKS: [string, number, number][] = [
  ["built", 0.2, 1],
  ["acc", 0.0, 4],
  ["sixteen", 0.9, 7],
  ["name", 0.0, 9],
]

function ProgressBar() {
  const f = useCurrentFrame()
  const { durationInFrames } = useVideoConfig()
  return (
    <AbsoluteFill style={{ justifyContent: "flex-start" }}>
      <div style={{ height: 6, width: `${(f / durationInFrames) * 100}%`, background: C.teal }} />
    </AbsoluteFill>
  )
}

export function DocDuelPromo() {
  const { u, vertical } = useLayout()
  const starts = SCENES.map(([, id]) => (id ? at(id) - LEAD : 0))
  return (
    <AbsoluteFill>
      <Wallpaper />
      {SCENES.map(([Scene, id], i) => {
        const start = starts[i]
        const dur = (starts[i + 1] ?? TOTAL_FRAMES) - start
        return (
          <Sequence key={id ?? "hook"} from={start} durationInFrames={dur} premountFor={15}>
            <AbsoluteFill style={{ scale: vertical ? 1.1 : 1, translate: vertical ? "0 -40px" : "0 0" }}>
              <Scene start={start} dur={dur} />
            </AbsoluteFill>
          </Sequence>
        )
      })}
      {LEAKS.map(([id, sec, seed]) => (
        <Sequence key={id} from={at(id, sec)} durationInFrames={30} premountFor={30}>
          <LightLeak seed={seed} />
        </Sequence>
      ))}
      <Captions />
      <ProgressBar />
      <div style={{ position: "absolute", right: 24 * u, top: 20 * u, fontFamily: MONO, fontSize: 20 * u, color: "rgba(243,238,228,0.5)" }}>
        docduel.vercel.app
      </div>
      <Audio
        src={staticFile("music.wav")}
        volume={(f) => interpolate(f, [0, 20, TOTAL_FRAMES - 45, TOTAL_FRAMES], [0, 0.2, 0.2, 0], { extrapolateRight: "clamp" })}
      />
      {timeline.clips.map((c) => (
        <Sequence key={c.id} from={Math.round(c.start * FPS)} durationInFrames={Math.ceil((c.file - c.offset) * FPS)} premountFor={FPS}>
          {/* trimBefore skips the clip's leading silence so the first word lands on c.start */}
          <Audio src={staticFile(`vo/${c.id}.mp3`)} trimBefore={Math.round(c.offset * FPS)} volume={1} />
        </Sequence>
      ))}
      {SFX.map(([name, id, word, s, vol], i) => (
        <Sequence key={i} from={Math.max(0, word ? atWord(id, word, s) : at(id, s))} durationInFrames={5 * FPS} premountFor={FPS}>
          <Audio src={staticFile(`sfx/${name}.wav`)} volume={vol ?? 0.45} />
        </Sequence>
      ))}
      <span style={{ display: "none", fontFamily: SANS }} />
    </AbsoluteFill>
  )
}
