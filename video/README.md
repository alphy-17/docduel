# DocDuel promo video

A 60-second narrated motion graphics video of DocDuel, written as code with [Remotion](https://www.remotion.dev): React components rendered frame by frame to MP4, in landscape (1920x1080) and vertical (1080x1920).

How it is made:

1. `make_voice.mjs` speaks `script.json` with [ElevenLabs](https://elevenlabs.io) (the voice Remotion's voiceover guide uses) and saves each line's MP3 plus its character timings.
2. `make_audio.py` synthesises the music and 17 sound effects from scratch (royalty free). The track follows the narration: the beat drops on "DocDuel", breaks down for "The result?" and dips under every spoken line.
3. `make_data.py` reads every number from `reports/*.json` (rule R5) and uses the character timings to place every scene, sound effect and caption word on the spoken words (`src/timeline.json`).
4. `src/Scenes.tsx` holds the nine scenes (hook, the race, data, training, result, the human loop, cost, deployment, end card); `src/Video.tsx` adds captions, light leaks, music, voice and effects.

```bash
# put ELEVENLABS_API_KEY=... in video/.env first (git-ignored; see .env.example)
cd video && npm ci && node make_voice.mjs && cd ..                  # about 900 characters of ElevenLabs credit
pip install numpy scipy
python video/make_data.py && python video/make_audio.py              # from the repo root
cd video
npx remotion studio src/index.ts                                     # preview and edit
npx remotion render src/index.ts landscape out/docduel_landscape.mp4
npx remotion render src/index.ts vertical out/docduel_vertical.mp4
# optional: lift loudness to about -14 LUFS for social media
ffmpeg -i out/docduel_vertical.mp4 -c:v copy -af "volume=7dB,alimiter=limit=0.85:level=false" -c:a aac -b:a 192k out/final_vertical.mp4
```

Remotion is free for individuals and small teams; check its licence before company use. Voice by ElevenLabs; the free plan asks for this credit.
