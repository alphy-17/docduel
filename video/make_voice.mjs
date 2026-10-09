// Narration with ElevenLabs (the voice Remotion's voiceover guide uses).
//
//   1. Put your key in video/.env as   ELEVENLABS_API_KEY=...   (the file is git-ignored)
//   2. cd video && node make_voice.mjs
//
// Speaks each line of script.json and writes public/vo/<id>.mp3 plus public/vo/<id>.json with the
// character timings, so make_data.py can sync scenes and captions to the real speech.
// Each request passes the lines before and after it, so the delivery flows like one take.
// Uses about 800 characters of your monthly allowance per full run.

import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const HERE = dirname(fileURLToPath(import.meta.url))
const env = existsSync(join(HERE, ".env")) ? readFileSync(join(HERE, ".env"), "utf8") : ""
for (const line of env.split(/\r?\n/)) {
  const m = line.match(/^\s*([A-Z_]+)\s*=\s*(.*?)\s*$/)
  if (m && !process.env[m[1]]) process.env[m[1]] = m[2].replace(/^["']|["']$/g, "")
}
const KEY = process.env.ELEVENLABS_API_KEY
if (!KEY) {
  console.error("No ELEVENLABS_API_KEY. Add it to video/.env first.")
  process.exit(1)
}
const VOICE = process.env.ELEVENLABS_VOICE_ID || "JBFqnCBsd6RMkjVDRZzb" // "George", a warm narrator voice
const MODEL = "eleven_multilingual_v2"
const only = process.argv.slice(2) // optional: node make_voice.mjs acc perfect   (redo just these lines)

const lines = JSON.parse(readFileSync(join(HERE, "script.json"), "utf8")).lines
const out = join(HERE, "public", "vo")
mkdirSync(out, { recursive: true })

for (const [i, line] of lines.entries()) {
  if (only.length && !only.includes(line.id)) continue
  const res = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${VOICE}/with-timestamps?output_format=mp3_44100_128`, {
    method: "POST",
    headers: { "xi-api-key": KEY, "Content-Type": "application/json" },
    body: JSON.stringify({
      text: line.say,
      model_id: MODEL,
      previous_text: lines.slice(Math.max(0, i - 2), i).map((l) => l.say).join(" ") || undefined,
      next_text: lines.slice(i + 1, i + 3).map((l) => l.say).join(" ") || undefined,
      voice_settings: { stability: 0.45, similarity_boost: 0.8, style: 0.35, use_speaker_boost: true, speed: 1.08 },
    }),
  })
  if (!res.ok) {
    console.error(`${line.id}: ElevenLabs said ${res.status} ${await res.text()}`)
    process.exit(1)
  }
  const body = await res.json()
  writeFileSync(join(out, `${line.id}.mp3`), Buffer.from(body.audio_base64, "base64"))
  writeFileSync(join(out, `${line.id}.json`), JSON.stringify({ say: line.say, alignment: body.alignment }) + "\n")
  console.log(`ok  ${line.id}`)
}
console.log("Done. Tell Claude the voice files are ready.")
