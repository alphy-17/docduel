import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame } from "remotion"

import data from "./data.json"
import { at, atWord, C, Card, Kicker, MONO, popStyle, SANS, SERIF, usePop, useLayout, useRamp, useSceneOut, Words } from "./kit"

export type SceneProps = { start: number; dur: number }
const pct = (v: number, d = 1) => `${(v * 100).toFixed(d)}%`
const usd = (v: number) => `$${v.toFixed(2)}`

/* 1. Hook: tiny model vs OpenAI, then the name slams in */
export function Hook({ start, dur }: SceneProps) {
  const f = useCurrentFrame()
  const { u, vertical } = useLayout()
  const r = (id: string, s = 0) => at(id, s) - start
  const cue = (id: string, word: string, s = 0) => atWord(id, word, s) - start
  const out = useSceneOut(dur)
  const small = usePop(cue("hook", "tiny", -0.1))
  const big = usePop(cue("hook", "OpenAI", -0.1))
  const vs = usePop(cue("hook", "read", -0.1))
  const slam = usePop(r("built", 0.25))
  const away = interpolate(f, [r("built", 0.1), r("built", 0.4)], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })
  const shake = f > r("built", 0.25) && f < r("built", 0.55) ? Math.sin(f * 3) * 8 * u : 0
  return (
    <AbsoluteFill style={{ opacity: out, alignItems: "center", justifyContent: "center", transform: `translateX(${shake}px)` }}>
      <div style={{ opacity: away, display: "flex", flexDirection: "column", alignItems: "center", gap: 50 * u }}>
        <Words text="Can a tiny model beat OpenAI?" from={r("hook", 0.05)} size={vertical ? 92 : 100} />
        <div style={{ display: "flex", alignItems: "center", gap: 46 * u }}>
          <div style={{ ...popStyle(small), width: 150 * u, height: 150 * u, borderRadius: 999, background: C.ours, display: "grid", placeItems: "center", fontFamily: MONO, fontSize: 40 * u, color: C.light }}>
            4B
          </div>
          <div style={{ ...popStyle(vs), fontFamily: SERIF, fontStyle: "italic", fontSize: 60 * u, color: C.dim }}>vs</div>
          <div style={{ ...popStyle(big), width: 330 * u, height: 330 * u, borderRadius: 999, background: C.openai, display: "grid", placeItems: "center", fontFamily: SANS, fontWeight: 600, fontSize: 44 * u, color: C.light }}>
            OpenAI
          </div>
        </div>
      </div>
      <div
        style={{
          position: "absolute",
          fontFamily: SERIF,
          fontWeight: 700,
          fontSize: (vertical ? 190 : 230) * u,
          color: C.light,
          opacity: Math.min(1, slam * 2),
          transform: `scale(${3 - 2 * slam})`,
        }}
      >
        Doc<span style={{ color: C.teal }}>Duel</span>
      </div>
    </AbsoluteFill>
  )
}

/* 2. The race: real screenshots of a recorded run with racing bars */
export function Race({ start, dur }: SceneProps) {
  const f = useCurrentFrame()
  const { u, vertical } = useLayout()
  const r = (s: number) => at("race", s) - start
  const out = useSceneOut(dur)
  const a = usePop(r(0.0))
  const b = usePop(r(0.75))
  const card = usePop(r(0.3), false)
  const openaiBar = useRamp(r(1.2), r(2.6))
  const oursBar = useRamp(r(1.2), r(3.7))
  const done = interpolate(f, [r(3.4), r(3.9)], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })
  const w = vertical ? 960 * u : 1500 * u
  const bar = (label: string, v: number, color: string) => (
    <div style={{ flex: 1 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontFamily: SANS, fontWeight: 500, fontSize: 28 * u, color: C.light }}>
        <span>{label}</span>
        <span style={{ color: v >= 1 ? C.green : C.dim }}>{v >= 1 ? "done" : "reading..."}</span>
      </div>
      <div style={{ height: 18 * u, marginTop: 10 * u, background: "rgba(0,0,0,0.3)", borderRadius: 99 }}>
        <div style={{ width: `${v * 100}%`, height: "100%", background: color, borderRadius: 99 }} />
      </div>
    </div>
  )
  return (
    <AbsoluteFill style={{ opacity: out, alignItems: "center", justifyContent: "center", gap: 36 * u, padding: 60 * u }}>
      <div style={{ display: "flex", gap: 30 * u, fontFamily: SERIF, fontWeight: 700, fontSize: (vertical ? 76 : 80) * u, color: C.light }}>
        <span style={popStyle(a)}>Same document.</span>
        {!vertical && <span style={popStyle(b)}>Same prompt.</span>}
      </div>
      {vertical && <div style={{ ...popStyle(b), fontFamily: SERIF, fontWeight: 700, fontSize: 76 * u, color: C.light }}>Same prompt.</div>}
      <div style={{ width: w, display: "flex", gap: 40 * u, opacity: card }}>
        {bar("Small model (mine)", oursBar, C.ours)}
        {bar("OpenAI", openaiBar, C.openai)}
      </div>
      <div style={{ position: "relative", width: w, height: (w * 1042) / 2400, transform: `translateY(${(1 - card) * 120}px)`, opacity: card }}>
        <Img src={staticFile("panels_2.png")} style={{ position: "absolute", width: "100%", opacity: 1 - done, borderRadius: 20 * u }} />
        <Img src={staticFile("panels_done.png")} style={{ position: "absolute", width: "100%", opacity: done, borderRadius: 20 * u }} />
      </div>
    </AbsoluteFill>
  )
}

/* 3. Data: receipts pour in, the test set gets locked away */
function Receipt({ x, y, rot, p, tint }: { x: number; y: number; rot: number; p: number; tint: string }) {
  const { u } = useLayout()
  return (
    <div
      style={{
        position: "absolute",
        left: x * u,
        top: y * u,
        width: 70 * u,
        height: 96 * u,
        background: C.cardSolid,
        borderTop: `${8 * u}px solid ${tint}`,
        borderRadius: 6 * u,
        boxShadow: "0 6px 14px rgba(0,0,0,0.35)",
        opacity: Math.min(1, p * 2),
        transform: `translateY(${(1 - p) * -500 * u}px) rotate(${rot}deg)`,
        padding: 8 * u,
      }}
    >
      {[0, 1, 2, 3].map((i) => (
        <div key={i} style={{ height: 5 * u, marginTop: 8 * u, width: `${90 - i * 15}%`, background: "#d4cbbb", borderRadius: 4 }} />
      ))}
    </div>
  )
}

export function Data({ start, dur }: SceneProps) {
  const f = useCurrentFrame()
  const { u, vertical } = useLayout()
  const r = (id: string, s = 0) => at(id, s) - start
  const cue = (id: string, word: string, s = 0) => atWord(id, word, s) - start
  const out = useSceneOut(dur)
  const head = usePop(r("data", 0))
  const c1 = useRamp(cue("data", "800", -0.15), cue("data", "800", 1.1))
  const c2 = useRamp(cue("data", "500", -0.15), cue("data", "500", 1.1))
  const vault = usePop(cue("data", "test", -0.1))
  const lock = useRamp(r("never", 0.0), r("never", 0.35))
  const stamp = usePop(r("never", 0.3))
  const piles = (n: number, from: number, x0: number, tint: string, seed: number) =>
    Array.from({ length: n }, (_, i) => {
      const p = Math.min(1, Math.max(0, (f - from - i * 2) / 10))
      const ease = 1 - Math.pow(1 - p, 3)
      return <Receipt key={i} x={x0 + ((i * 37 + seed) % 120)} y={120 - i * 6} rot={((i * 53 + seed) % 30) - 15} p={ease} tint={tint} />
    })
  const col = (count: number, label: string, v: number, tint: string, from: number, seed: number) => (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", width: vertical ? 440 * u : 420 * u }}>
      <div style={{ position: "relative", width: 260 * u, height: 260 * u }}>{piles(14, from, 30, tint, seed)}</div>
      <div style={{ fontFamily: MONO, fontWeight: 500, fontSize: 96 * u, color: C.light, lineHeight: 1 }}>{Math.round(count * v)}</div>
      <div style={{ fontFamily: SANS, fontSize: 30 * u, color: C.dim, textAlign: "center", marginTop: 8 * u }}>{label}</div>
    </div>
  )
  return (
    <AbsoluteFill style={{ opacity: out, alignItems: "center", justifyContent: "center", gap: 40 * u, padding: 60 * u }}>
      <div style={popStyle(head)}>
        <Kicker>Step 1: the data</Kicker>
      </div>
      <div style={{ display: "flex", flexDirection: vertical ? "column" : "row", alignItems: "center", gap: 40 * u }}>
        <div style={{ display: "flex", gap: 30 * u }}>
          {col(data.cordTrain, "real receipts", c1, C.amber, cue("data", "800", -0.15), 7)}
          {col(data.synthTrain, "invoices I generated", c2, C.teal, cue("data", "500", -0.15), 19)}
        </div>
        <div style={{ ...popStyle(vault), position: "relative", display: "flex", flexDirection: "column", alignItems: "center", width: 420 * u }}>
          <svg width={220 * u} height={250 * u} viewBox="0 0 220 250">
            <path
              d={`M60 ${130 - 0} V80 a50 50 0 0 1 100 0 V${130 - 40 * (1 - lock)}`}
              fill="none"
              stroke={C.light}
              strokeWidth="18"
              strokeLinecap="round"
              transform={`translate(0 ${-30 * (1 - lock)})`}
            />
            <rect x="25" y="115" width="170" height="125" rx="22" fill={C.teal} />
            <circle cx="110" cy="170" r="16" fill={C.base} />
            <rect x="103" y="175" width="14" height="34" rx="6" fill={C.base} />
          </svg>
          <div style={{ fontFamily: SANS, fontWeight: 500, fontSize: 32 * u, color: C.light, textAlign: "center", marginTop: 10 * u }}>
            Test set, frozen
            <br />
            <span style={{ color: C.dim, fontWeight: 400, fontSize: 26 * u }}>{data.testDocs} receipts and invoices</span>
          </div>
          <div
            style={{
              position: "absolute",
              top: 90 * u,
              padding: `${10 * u}px ${22 * u}px`,
              border: `${5 * u}px solid ${C.red}`,
              borderRadius: 12 * u,
              color: C.red,
              background: "rgba(29,38,51,0.85)",
              fontFamily: SANS,
              fontWeight: 700,
              fontSize: 34 * u,
              letterSpacing: 2 * u,
              opacity: Math.min(1, stamp * 2),
              transform: `rotate(-12deg) scale(${2.2 - 1.2 * stamp})`,
              whiteSpace: "nowrap",
            }}
          >
            NEVER TRAINED ON
          </div>
        </div>
      </div>
    </AbsoluteFill>
  )
}

/* 4. Training: model + adapter, GPU, a real loss curve, time and cost */
export function Train({ start, dur }: SceneProps) {
  const f = useCurrentFrame()
  const { u, vertical } = useLayout()
  const r = (id: string, s = 0) => at(id, s) - start
  const cue = (id: string, word: string, s = 0) => atWord(id, word, s) - start
  const out = useSceneOut(dur)
  const title = usePop(r("train", 0))
  const model = usePop(cue("qwen", "Qwen", -0.1))
  const lora = usePop(cue("qwen", "open", -0.1))
  const gpu = usePop(cue("qwen", "rented", -0.1))
  const draw = useRamp(cue("qwen", "rented", 0.1), cue("forty", "About", 0.4), (x) => x)
  const t1 = usePop(cue("forty", "39", -0.1))
  const t2 = usePop(cue("forty", "About", -0.1))
  const W = (vertical ? 860 : 760) * u
  const H = (vertical ? 300 : 300) * u
  const max = Math.max(...data.loss)
  const pts = data.loss.map((v, i) => [(i / (data.loss.length - 1)) * W, H - (v / max) * H * 0.92])
  const n = Math.max(2, Math.ceil(draw * pts.length))
  const path = pts.slice(0, n).map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ")
  const util = (k: number) => 0.55 + 0.4 * Math.abs(Math.sin(f / (5 + k)))
  const tile = (p: number, big: string, small: string, color: string) => (
    <div style={{ ...popStyle(p), background: "rgba(0,0,0,0.3)", borderRadius: 24 * u, padding: `${18 * u}px ${34 * u}px`, textAlign: "center" }}>
      <div style={{ fontFamily: MONO, fontWeight: 500, fontSize: 80 * u, color }}>{big}</div>
      <div style={{ fontFamily: SANS, fontSize: 26 * u, color: C.dim }}>{small}</div>
    </div>
  )
  return (
    <AbsoluteFill style={{ opacity: out, alignItems: "center", justifyContent: "center", gap: 40 * u, padding: 60 * u }}>
      <div style={popStyle(title)}>
        <Kicker>Step 2: training</Kicker>
      </div>
      <div style={{ display: "flex", flexDirection: vertical ? "column" : "row", alignItems: "center", gap: 50 * u }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 * u }}>
          <div style={{ ...popStyle(model), background: C.ours, color: C.light, borderRadius: 26 * u, padding: `${30 * u}px ${36 * u}px`, fontFamily: SANS, fontWeight: 600, fontSize: 40 * u, textAlign: "center" }}>
            Qwen3.5
            <div style={{ fontFamily: MONO, fontWeight: 500, fontSize: 30 * u, opacity: 0.85 }}>4B open model</div>
          </div>
          <div style={{ ...popStyle(lora, 0), fontFamily: SANS, fontSize: 50 * u, color: C.dim }}>+</div>
          <div style={{ ...popStyle(lora), background: C.teal, color: C.base, borderRadius: 26 * u, padding: `${30 * u}px ${32 * u}px`, fontFamily: SANS, fontWeight: 600, fontSize: 40 * u, textAlign: "center" }}>
            LoRA
            <div style={{ fontFamily: MONO, fontWeight: 500, fontSize: 30 * u, opacity: 0.85 }}>my adapter</div>
          </div>
        </div>
        <div style={{ ...popStyle(gpu), display: "flex", alignItems: "flex-end", gap: 10 * u, background: "rgba(0,0,0,0.3)", padding: 22 * u, borderRadius: 20 * u }}>
          <div style={{ fontFamily: MONO, fontSize: 30 * u, color: C.light, marginRight: 10 * u }}>{data.gpu}<br /><span style={{ color: C.dim, fontSize: 22 * u }}>GPU</span></div>
          {[0, 1, 2, 3, 4, 5].map((k) => (
            <div key={k} style={{ width: 18 * u, height: 90 * u * util(k), background: C.green, borderRadius: 4 * u }} />
          ))}
        </div>
      </div>
      <div style={{ opacity: gpu, position: "relative" }}>
        <div style={{ fontFamily: SANS, fontSize: 24 * u, color: C.dim, marginBottom: 8 * u }}>training loss, real run ({data.trainExamples.toLocaleString("en")} examples)</div>
        <svg width={W} height={H} style={{ overflow: "visible" }}>
          <line x1={0} y1={H} x2={W} y2={H} stroke="rgba(243,238,228,0.3)" strokeWidth={2} />
          <path d={path} fill="none" stroke={C.teal} strokeWidth={5 * u} strokeLinejoin="round" strokeLinecap="round" />
        </svg>
      </div>
      <div style={{ display: "flex", gap: 30 * u }}>
        {tile(t1, `${data.trainMinutes} min`, "of training", C.light)}
        {tile(t2, usd(data.trainUsd ?? 0), "of GPU time", C.teal)}
      </div>
    </AbsoluteFill>
  )
}

/* 5. The result: drumroll, then the gauge */
export function Result({ start, dur }: SceneProps) {
  const f = useCurrentFrame()
  const { u, vertical } = useLayout()
  const r = (id: string, s = 0) => at(id, s) - start
  const cue = (id: string, word: string, s = 0) => atWord(id, word, s) - start
  const out = useSceneOut(dur)
  const q = usePop(r("result", 0))
  const qOut = interpolate(f, [r("acc", -0.1), r("acc", 0.1)], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })
  const sweep = useRamp(r("acc", 0), r("acc", 1.4))
  const pills = usePop(r("acc", 1.6))
  const R = (vertical ? 300 : 260) * u
  const circ = 2 * Math.PI * R
  const v = data.ratio * sweep
  return (
    <AbsoluteFill style={{ opacity: out, alignItems: "center", justifyContent: "center" }}>
      <div style={{ position: "absolute", ...popStyle(q), opacity: Math.min(1, q * 1.6) * qOut }}>
        <Words text="The result?" from={r("result", 0)} size={vertical ? 120 : 130} />
      </div>
      <div style={{ opacity: 1 - qOut, display: "flex", flexDirection: "column", alignItems: "center", gap: 30 * u }}>
        <div style={{ position: "relative", width: R * 2 + 40 * u, height: R * 2 + 40 * u }}>
          <svg width="100%" height="100%" viewBox={`0 0 ${R * 2 + 40 * u} ${R * 2 + 40 * u}`} style={{ transform: "rotate(-90deg)" }}>
            <circle cx={R + 20 * u} cy={R + 20 * u} r={R} fill="none" stroke="rgba(0,0,0,0.3)" strokeWidth={28 * u} />
            <circle cx={R + 20 * u} cy={R + 20 * u} r={R} fill="none" stroke={C.teal} strokeWidth={28 * u} strokeLinecap="round" strokeDasharray={`${circ * v} ${circ}`} />
          </svg>
          <div style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", textAlign: "center" }}>
            <div>
              <div style={{ fontFamily: SERIF, fontWeight: 700, fontSize: (vertical ? 150 : 130) * u, color: C.light, lineHeight: 1 }}>{pct(v)}</div>
              <div style={{ fontFamily: SANS, fontSize: 32 * u, color: C.dim, marginTop: 10 * u }}>of OpenAI's accuracy</div>
            </div>
          </div>
        </div>
        <div style={{ ...popStyle(pills), display: "flex", gap: 20 * u, fontFamily: SANS, fontSize: 30 * u, color: C.light }}>
          <span>
            <span style={{ color: C.ours }}>●</span> Mine <span style={{ fontFamily: MONO }}>{pct(data.oursField)}</span>
          </span>
          <span>
            <span style={{ color: C.openai }}>●</span> OpenAI <span style={{ fontFamily: MONO }}>{pct(data.openaiField)}</span>
          </span>
        </div>
        <div style={{ ...popStyle(pills), fontFamily: SANS, fontSize: 24 * u, color: C.dim }}>field accuracy on {data.testDocs} held-out receipts and invoices</div>
      </div>
    </AbsoluteFill>
  )
}

/* 6. The human loop: a real mistake, 40 corrections, the jump */
export function Loop({ start, dur }: SceneProps) {
  const f = useCurrentFrame()
  const { u, vertical } = useLayout()
  const r = (id: string, s = 0) => at(id, s) - start
  const cue = (id: string, word: string, s = 0) => atWord(id, word, s) - start
  const out = useSceneOut(dur)
  const inv = usePop(r("layout", 0), false)
  const scan = useRamp(r("layout", 0.3), r("layout", 1.3), (x) => x)
  const wrong = usePop(cue("layout", "tripped", -0.1))
  const gridIn = usePop(cue("layout", "So", -0.1), false)
  const fixed = useRamp(cue("layout", "fixed", 0), cue("layout", "retrained", 0), (x) => x)
  const bars = usePop(r("perfect", 0))
  const b1 = useRamp(cue("perfect", "10%", -0.3), cue("perfect", "10%", 0.3))
  const b2 = useRamp(cue("perfect", "70%", -0.3), cue("perfect", "70%", 0.6))
  const shake = f > cue("layout", "tripped", -0.1) && f < cue("layout", "tripped", 0.25) ? Math.sin(f * 2.5) * 10 * u : 0
  const line = (label: string, value: string, extra?: React.ReactNode) => (
    <div style={{ display: "flex", justifyContent: "space-between", fontFamily: MONO, fontSize: 26 * u, color: C.ink, padding: `${6 * u}px 0`, borderBottom: `1px solid #e0d7c7` }}>
      <span style={{ color: C.ink2 }}>{label}</span>
      <span>{value}{extra}</span>
    </div>
  )
  const bar = (label: string, v: number, p: number, color: string) => (
    <div style={{ marginTop: 18 * u }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontFamily: SANS, fontSize: 30 * u, color: C.light }}>
        <span>{label}</span>
        <span style={{ fontFamily: MONO }}>{pct(v * p, 0)}</span>
      </div>
      <div style={{ height: 30 * u, marginTop: 8 * u, background: "rgba(0,0,0,0.3)", borderRadius: 99 }}>
        <div style={{ width: `${v * 100 * p}%`, height: "100%", background: color, borderRadius: 99 }} />
      </div>
    </div>
  )
  return (
    <AbsoluteFill style={{ opacity: out, alignItems: "center", justifyContent: "center", gap: 36 * u, padding: 60 * u }}>
      <Kicker>Step 3: human in the loop</Kicker>
      <div style={{ display: "flex", flexDirection: vertical ? "column" : "row", alignItems: "center", gap: 50 * u }}>
        <div style={{ position: "relative", ...popStyle(inv), transform: `${popStyle(inv).transform} translateX(${shake}px)` }}>
          <Card style={{ width: 520 * u, padding: 28 * u, background: C.cardSolid }}>
            <div style={{ fontFamily: SANS, fontWeight: 600, fontSize: 26 * u, color: C.ink }}>Granite Office Supplies</div>
            <div style={{ fontFamily: MONO, fontSize: 22 * u, color: C.ink2, marginBottom: 10 * u }}>Ref:A56115 Dt:03/22/2026</div>
            {line("Date read as", "2026-02-03", <span style={{ color: C.red, fontWeight: 700, opacity: wrong }}> ✗</span>)}
            {line("Should be", "2026-03-22")}
            <div
              style={{
                position: "absolute",
                left: 0,
                right: 0,
                top: `${scan * 100}%`,
                height: 6 * u,
                background: C.teal,
                boxShadow: `0 0 ${24 * u}px ${C.teal}`,
                opacity: scan > 0 && scan < 1 ? 1 : 0,
              }}
            />
          </Card>
          <div style={{ ...popStyle(wrong), fontFamily: SANS, fontSize: 26 * u, color: C.red, marginTop: 12 * u, textAlign: "center" }}>
            US-style date, a layout it never saw
          </div>
        </div>
        <div style={{ opacity: gridIn, display: "flex", flexDirection: "column", alignItems: "center" }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(10, 1fr)", gap: 10 * u }}>
            {Array.from({ length: data.corrections }, (_, i) => {
              const on = fixed * data.corrections > i
              return <div key={i} style={{ width: 34 * u, height: 34 * u, borderRadius: 8 * u, background: on ? C.green : "rgba(0,0,0,0.3)", transform: `scale(${on ? 1 : 0.85})` }} />
            })}
          </div>
          <div style={{ fontFamily: SANS, fontSize: 28 * u, color: C.light, marginTop: 14 * u }}>
            <span style={{ fontFamily: MONO }}>{Math.min(data.corrections, Math.ceil(fixed * data.corrections))}</span> / {data.corrections} corrected by hand
          </div>
        </div>
      </div>
      <div style={{ ...popStyle(bars), width: (vertical ? 900 : 1100) * u }}>
        <div style={{ fontFamily: SANS, fontSize: 26 * u, color: C.dim }}>Perfect documents on new invoices of that layout</div>
        {bar("Before", data.hardPerfectR1, b1, C.dim)}
        {bar("After my corrections", data.hardPerfectR2, b2, C.teal)}
      </div>
    </AbsoluteFill>
  )
}

/* 7. Cost: the honest answer */
export function Cost({ start, dur }: SceneProps) {
  const f = useCurrentFrame()
  const { u, vertical } = useLayout()
  const r = (id: string, s = 0) => at(id, s) - start
  const cue = (id: string, word: string, s = 0) => atWord(id, word, s) - start
  const out = useSceneOut(dur)
  const q = usePop(r("cheaper", 0))
  const no = usePop(cue("one", "No", -0.05))
  const yes = usePop(cue("sixteen", "beats", -0.1))
  const H = (vertical ? 620 : 420) * u
  const max = 1.4
  const grow = (i: number) => {
    const from = i === 0 ? r("one", 0) : cue("sixteen", "16", (i - 1) * 0.3)
    return interpolate(f, [from, from + 10], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })
  }
  const lineY = H * (1 - data.openaiUsd / max)
  return (
    <AbsoluteFill style={{ opacity: out, alignItems: "center", justifyContent: "center", gap: 34 * u, padding: 60 * u }}>
      <div style={popStyle(q)}>
        <Words text="Is it cheaper?" from={r("cheaper", 0)} size={vertical ? 96 : 90} />
      </div>
      <Card style={{ width: (vertical ? 960 : 1300) * u, padding: `${36 * u}px ${44 * u}px ${24 * u}px`, background: C.cardSolid }}>
        <div style={{ position: "relative", height: H, display: "flex", alignItems: "flex-end", gap: 50 * u }}>
          <div style={{ position: "absolute", left: 0, right: 0, top: lineY, borderTop: `${4 * u}px dashed ${C.openai}` }} />
          {data.throughput.map((t, i) => {
            const g = grow(i)
            const cheaper = t.usd < data.openaiUsd
            return (
              <div key={t.c} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "flex-end", height: "100%" }}>
                <div style={{ position: "relative", fontFamily: MONO, fontSize: 34 * u, color: C.ink, opacity: g, background: C.cardSolid, padding: `0 ${8 * u}px`, borderRadius: 8 * u, marginBottom: 8 * u }}>
                  {usd(t.usd)}
                </div>
                <div style={{ position: "relative", width: "100%", height: H * (t.usd / max) * g, background: cheaper ? C.brand : C.ours, borderRadius: `${12 * u}px ${12 * u}px 0 0` }} />
              </div>
            )
          })}
        </div>
        <div style={{ display: "flex", gap: 50 * u, borderTop: "2px solid #d9d1c3", paddingTop: 12 * u }}>
          {data.throughput.map((t) => (
            <div key={t.c} style={{ flex: 1, textAlign: "center", fontFamily: SANS, fontSize: 26 * u, color: C.ink2 }}>
              {t.c} at once
            </div>
          ))}
        </div>
        <div style={{ marginTop: 12 * u, fontFamily: SANS, fontWeight: 500, fontSize: 24 * u, color: C.openai }}>
          - - - OpenAI {usd(data.openaiUsd)} per 1,000 documents, at any volume
        </div>
      </Card>
      <div style={{ position: "relative", height: 90 * u, width: "100%", display: "grid", placeItems: "center" }}>
        <div style={{ position: "absolute", ...popStyle(no), opacity: Math.min(1, no * 2) * (1 - yes), fontFamily: SERIF, fontWeight: 700, fontSize: 64 * u, color: C.red }}>
          One at a time? No.
        </div>
        <div style={{ position: "absolute", ...popStyle(yes), fontFamily: SERIF, fontWeight: 700, fontSize: 64 * u, color: C.teal }}>
          16 at once? Cheaper.
        </div>
      </div>
    </AbsoluteFill>
  )
}

/* 8. Live: the stack snaps together, the site flies in */
export function Live({ start, dur }: SceneProps) {
  const { u, vertical } = useLayout()
  const r = (s: number) => at("live", s) - start
  const cue = (word: string, s = 0) => atWord("live", word, s) - start
  const out = useSceneOut(dur)
  const site = usePop(r(0.1), false)
  const tiles = [
    ["React", "on Vercel", "React"],
    ["FastAPI", "on Azure", "API"],
    ["Qwen + vLLM", "on Modal GPU", "model"],
  ] as const
  const pops = [usePop(cue(tiles[0][2], -0.1)), usePop(cue(tiles[1][2], -0.1)), usePop(cue(tiles[2][2], -0.1))]
  const w = (vertical ? 900 : 980) * u
  return (
    <AbsoluteFill style={{ opacity: out, alignItems: "center", justifyContent: "center", gap: 40 * u, padding: 60 * u, paddingBottom: (vertical ? 260 : 140) * u }}>
      <Kicker>Step 4: ship it</Kicker>
      <div style={{ display: "flex", flexDirection: vertical ? "column" : "row", alignItems: "center", gap: 50 * u }}>
      <div style={{ ...popStyle(site), width: w, borderRadius: 18 * u, overflow: "hidden", boxShadow: "0 30px 70px rgba(0,0,0,0.5)" }}>
        <div style={{ background: "#2a2f38", padding: `${12 * u}px ${18 * u}px`, display: "flex", alignItems: "center", gap: 10 * u }}>
          {[C.red, C.amber, C.green].map((c) => (
            <span key={c} style={{ width: 14 * u, height: 14 * u, borderRadius: 99, background: c }} />
          ))}
          <span style={{ marginLeft: 16 * u, flex: 1, background: "#1d2128", color: C.dim, fontFamily: MONO, fontSize: 22 * u, borderRadius: 8 * u, padding: `${6 * u}px ${14 * u}px` }}>
            docduel.vercel.app
          </span>
        </div>
        <Img src={staticFile("home.png")} style={{ width: "100%", display: "block" }} />
      </div>
      <div style={{ display: "flex", flexDirection: vertical ? "row" : "column", flexWrap: "wrap", justifyContent: "center", alignItems: "center", gap: 18 * u }}>
        {tiles.map(([a, b], i) => (
          <div key={a} style={{ display: "flex", alignItems: "center", gap: 18 * u }}>
            {i > 0 && !vertical && <div style={{ position: "absolute", width: 4 * u, height: 18 * u, marginTop: -60 * u, background: C.teal, opacity: pops[i] }} />}
            <div style={{ ...popStyle(pops[i]), background: "rgba(0,0,0,0.35)", border: `2px solid ${C.teal}`, borderRadius: 18 * u, padding: `${14 * u}px ${26 * u}px`, textAlign: "center" }}>
              <div style={{ fontFamily: SANS, fontWeight: 600, fontSize: 34 * u, color: C.light }}>{a}</div>
              <div style={{ fontFamily: SANS, fontSize: 24 * u, color: C.dim }}>{b}</div>
            </div>
          </div>
        ))}
      </div>
      </div>
    </AbsoluteFill>
  )
}

/* 9. End card */
export function End({ start }: SceneProps) {
  const { u, vertical } = useLayout()
  const r = (id: string, s = 0) => at(id, s) - start
  const cue = (id: string, word: string, s = 0) => atWord(id, word, s) - start
  const logo = usePop(r("name", 0))
  const url = usePop(r("try", 0.2))
  const sub = usePop(r("try", 0.9))
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", textAlign: "center", gap: 20 * u, padding: 60 * u }}>
      <div style={{ ...popStyle(logo), fontFamily: SERIF, fontWeight: 700, fontSize: (vertical ? 170 : 200) * u, color: C.light }}>
        Doc<span style={{ color: C.teal }}>Duel</span>
      </div>
      <div style={{ ...popStyle(url), fontFamily: MONO, fontSize: 56 * u, color: C.light, background: C.brand, padding: `${12 * u}px ${30 * u}px`, borderRadius: 16 * u }}>
        docduel.vercel.app
      </div>
      <div style={{ ...popStyle(sub), fontFamily: SANS, fontSize: 32 * u, lineHeight: 1.6, color: C.dim, marginTop: 10 * u }}>
        Code and every number: github.com/alphy-17/docduel
        <br />
        Built by Alphy Baby
        <div style={{ fontSize: 20 * u, opacity: 0.7 }}>Voice: ElevenLabs</div>
      </div>
    </AbsoluteFill>
  )
}
