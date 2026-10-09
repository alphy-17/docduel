"""Music and sound effects for the promo video, synthesised from scratch (royalty free).

  python video/make_audio.py      (after make_data.py: the music follows src/timeline.json)

The track is arranged around the narration: a filtered intro under the hook, the beat drops on
"DocDuel", drums fall away for "The result?" and slam back on the accuracy number, and the music
dips under every spoken line so the voice stays clear.
"""

import json
import wave
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfilt

SR = 44100
HERE = Path(__file__).parent
OUT = HERE / "public"
rng = np.random.default_rng(7)


def save(name: str, x: np.ndarray, peak: float | None = None) -> None:
    if peak:
        x = x / (np.max(np.abs(x)) + 1e-9) * peak
    x = np.clip(x, -1, 1)
    stereo = x.ndim == 2
    (OUT / name).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT / name), "wb") as w:
        w.setnchannels(2 if stereo else 1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


def ts(seconds: float) -> np.ndarray:
    return np.arange(int(SR * seconds)) / SR


def lp(x: np.ndarray, hz: float, order: int = 2) -> np.ndarray:
    return sosfilt(butter(order, hz, "low", fs=SR, output="sos"), x)


def hp(x: np.ndarray, hz: float, order: int = 2) -> np.ndarray:
    return sosfilt(butter(order, hz, "high", fs=SR, output="sos"), x)


def bp(x: np.ndarray, lo: float, hi: float) -> np.ndarray:
    return sosfilt(butter(2, [lo, hi], "band", fs=SR, output="sos"), x)


def noise(seconds: float) -> np.ndarray:
    return rng.standard_normal(int(SR * seconds))


def place(track: np.ndarray, sig: np.ndarray, at: float, pan: float = 0.0) -> None:
    """Mix a mono or stereo signal into a stereo track at `at` seconds; pan -1 (left) .. 1 (right)."""
    i = int(at * SR)
    if i >= len(track) or i + len(sig) <= 0:
        return
    if sig.ndim == 1:
        sig = np.stack([sig * np.sqrt((1 - pan) / 2), sig * np.sqrt((1 + pan) / 2)], axis=1)
    j0 = max(0, -i)
    j1 = min(len(sig), len(track) - i)
    track[i + j0 : i + j1] += sig[j0:j1]


def swept(x: np.ndarray, freqs: np.ndarray) -> np.ndarray:
    """Band-pass noise whose centre follows `freqs` (one value per chunk)."""
    out = np.zeros_like(x)
    for i, f in enumerate(freqs):
        a, z = i * len(x) // len(freqs), (i + 1) * len(x) // len(freqs)
        out[a:z] = bp(x, f * 0.7, min(f * 1.35, 19000))[a:z]
    return out


# ---------------------------------------------------------------- instruments

def kick() -> np.ndarray:
    t = ts(0.4)
    body = np.sin(2 * np.pi * np.cumsum(45 + 110 * np.exp(-t * 35)) / SR) * np.exp(-t * 8)
    return body + hp(noise(0.4), 3000) * np.exp(-t * 300) * 0.3


def clap() -> np.ndarray:
    t = ts(0.3)
    e = sum(np.exp(-np.maximum(t - d, 0) * 60) * (t >= d) for d in (0, 0.011, 0.022)) / 2 + np.exp(-t * 18) * 0.5
    return bp(noise(0.3), 900, 5000) * e * 0.55


def hat(open_: bool = False) -> np.ndarray:
    length = 0.25 if open_ else 0.05
    return hp(noise(length), 7000) * np.exp(-ts(length) * (14 if open_ else 90)) * 0.35


def pluck(f: float, seconds: float = 0.6) -> np.ndarray:
    """Karplus-Strong plucked string."""
    n, period = int(SR * seconds), int(SR / f)
    buf = list(rng.uniform(-1, 1, period))
    out = np.empty(n)
    for i in range(n):
        j = i % period
        out[i] = buf[j]
        buf[j] = 0.497 * (buf[j] + buf[(j + 1) % period])
    return lp(out, 3500) * 0.5


def pad(freqs: tuple[float, ...], seconds: float) -> np.ndarray:
    t = ts(seconds)
    left, right = np.zeros_like(t), np.zeros_like(t)
    for f in freqs:
        for k, amp in ((1, 1.0), (2, 0.35), (3, 0.18), (4, 0.08)):
            left += amp * np.sin(2 * np.pi * f * k * 0.998 * t)
            right += amp * np.sin(2 * np.pi * f * k * 1.002 * t + 0.7)
    shape = np.minimum(t / 0.25, 1) * np.minimum((seconds - t) / 0.25, 1)
    return np.stack([lp(left, 2200), lp(right, 2200)], axis=1) * shape[:, None] / (len(freqs) * 1.6)


def music(total: float, clips: dict, bpm: int = 112) -> np.ndarray:
    n = int(SR * total)
    drums, harm = np.zeros((n, 2)), np.zeros((n, 2))
    beat = 60 / bpm
    bar = 4 * beat
    drop = clips["built"]["start"]  # the beat drops on "DocDuel"
    brk0 = clips["result"]["start"] - 0.4  # breakdown under "The result?"
    brk1 = clips["acc"]["start"]  # ...and back on the number
    end = clips["name"]["start"]  # final hit on the end card
    first = drop - np.ceil(drop / beat) * beat  # grid that puts a downbeat exactly on the drop

    chords = [(220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (130.81, 164.81, 196.0), (196.0, 246.94, 293.66)]
    K, C, HO = kick(), clap(), hat(True)

    def grooving(t: float) -> bool:
        return drop - 0.01 <= t < end and not (brk0 <= t < brk1)

    k = 0
    while (t := first + k * beat) < total:
        if grooving(t):
            place(drums, K, t)
            if k % 2:
                place(drums, C, t, 0.1)
            place(drums, hat() * 0.8, t + beat / 2, 0.3)
            place(drums, hat() * 0.45, t + beat * 0.25, -0.3)
            place(drums, hat() * 0.45, t + beat * 0.75, -0.3)
            if k % 4 == 3:
                place(drums, HO * 0.6, t + beat / 2, 0.4)
        elif 1.0 < t < drop:
            place(drums, hat() * 0.35, t + beat / 2, 0.3)  # soft ticking intro
        k += 1
    if end < total:
        place(drums, K * 1.2, end)

    b = 0
    while (t0 := first + b * bar) < total:
        c = chords[b % 4]
        place(harm, pad(c, bar + 0.25), t0)
        tb = ts(bar)
        bass = (np.sin(2 * np.pi * c[0] / 2 * tb) + 0.3 * np.sin(2 * np.pi * c[0] * tb)) * np.minimum(tb / 0.02, 1) * 0.45
        place(harm, bass, t0)
        if grooving(t0):
            notes = [c[0] * 2, c[1] * 2, c[2] * 2, c[1] * 2, c[0] * 4, c[2] * 2, c[1] * 2, c[2] * 2]
            for i, f in enumerate(notes):
                place(harm, pluck(f) * 0.55, t0 + i * beat / 2, -0.5 if i % 2 else 0.5)
        b += 1

    t = np.arange(n) / SR
    groove = (t >= drop) & (t < end) & ~((t >= brk0) & (t < brk1))
    phase = ((t - first) % beat) / beat
    harm *= np.where(groove, 1 - 0.45 * np.exp(-phase * 8), 1)[:, None]  # sidechain pump
    for mask, hz in ((t < drop, 700), ((t >= brk0) & (t < brk1), 900)):  # muffled intro and breakdown
        harm[mask] = np.stack([lp(harm[mask, 0], hz), lp(harm[mask, 1], hz)], axis=1)

    mix = drums * 0.9 + harm * 0.75
    speech = np.zeros(n)
    for cl in clips.values():
        speech[int(cl["start"] * SR) : int((cl["start"] + cl["dur"]) * SR)] = 1
    win = int(SR * 0.25)
    speech = np.convolve(speech, np.ones(win) / win, mode="same")
    mix *= (1 - 0.42 * np.clip(speech, 0, 1))[:, None]  # dip under the voice
    fade = np.minimum(t / 1.2, 1) * np.clip((total - t) / 2.5, 0, 1)
    return mix * fade[:, None]


# ---------------------------------------------------------------- sound effects

def whoosh(length: float = 0.55) -> np.ndarray:
    t = ts(length)
    x = swept(noise(length), 400 + 3600 * np.sin(np.pi * (np.arange(24) + 0.5) / 24)) * np.sin(np.pi * t / length) ** 3
    return np.stack([x * np.linspace(1, 0.2, len(t)), x * np.linspace(0.2, 1, len(t))], axis=1)


def pop() -> np.ndarray:
    t = ts(0.12)
    return np.sin(2 * np.pi * (500 + 700 * np.exp(-t * 60)) * t) * np.exp(-t * 40)


def tick() -> np.ndarray:
    t = ts(0.04)
    return np.sin(2 * np.pi * 2200 * t) * np.exp(-t * 120)


def riser(length: float = 1.6) -> np.ndarray:
    t = ts(length)
    air = swept(noise(length), 300 * 20 ** (np.arange(32) / 32))
    tone_ = np.sin(2 * np.pi * np.cumsum(220 * 4 ** (t / length)) / SR) * 0.25
    return (air * 0.8 + tone_) * (t / length) ** 2


def impact() -> np.ndarray:
    t = ts(1.2)
    body = np.sin(2 * np.pi * np.cumsum(38 + 70 * np.exp(-t * 14)) / SR) * np.exp(-t * 3.5)
    return body + hp(noise(1.2), 4000) * np.exp(-t * 4) * 0.25 + lp(noise(1.2), 600) * np.exp(-t * 20) * 0.4


def ding() -> np.ndarray:
    t = ts(0.9)
    return sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t * d) for f, a, d in ((1318.5, 1, 5), (2637, 0.3, 9), (3951, 0.12, 14)))


def typing(length: float = 2.4) -> np.ndarray:
    out, t = np.zeros(int(SR * length)), 0.0
    while t < length - 0.05:
        click = bp(noise(0.03), 1500, 6000) * np.exp(-ts(0.03) * 220) * rng.uniform(0.5, 1)
        thock = np.sin(2 * np.pi * rng.uniform(180, 260) * ts(0.03)) * np.exp(-ts(0.03) * 150) * 0.5
        i = int(t * SR)
        out[i : i + len(click)] += (click + thock)[: len(out) - i]
        t += rng.choice([0.07, 0.09, 0.11, 0.16, 0.28], p=[0.3, 0.3, 0.2, 0.15, 0.05])
    return out * np.minimum(ts(length) / 0.1, 1) * np.minimum((length - ts(length)) / 0.3, 1)


def paper(length: float = 1.4) -> np.ndarray:
    t = ts(length)
    crackle = (rng.random(len(t)) < 0.012) * rng.standard_normal(len(t))
    rustle = bp(noise(length), 1500, 8000) * (0.3 + 0.7 * np.abs(np.sin(t * 9)))
    return (bp(crackle, 2000, 9000) * 2 + rustle * 0.5) * np.sin(np.pi * t / length)


def stamp() -> np.ndarray:
    t = ts(0.6)
    thud = np.sin(2 * np.pi * np.cumsum(70 + 90 * np.exp(-t * 40)) / SR) * np.exp(-t * 12)
    return thud + bp(noise(0.6), 800, 4000) * np.exp(-t * 60) * 0.8


def lock() -> np.ndarray:
    t = ts(0.25)
    second = np.zeros_like(t)
    i = int(0.09 * SR)
    second[i:] = (bp(noise(0.25), 3000, 10000) * np.exp(-t * 160))[: len(t) - i]
    return bp(noise(0.25), 2500, 9000) * np.exp(-t * 200) * 0.7 + second + np.sin(2 * np.pi * 3100 * t) * np.exp(-t * 30) * 0.15


def hum(length: float = 4.5) -> np.ndarray:
    """A GPU spinning up: fan noise plus a rising electrical whine."""
    t = ts(length)
    spin = np.minimum(t / 1.2, 1)
    fan = lp(noise(length), 900) * (0.4 + 0.6 * spin)
    whine = np.sin(2 * np.pi * np.cumsum(120 + 260 * spin) / SR) * 0.25 + np.sin(2 * np.pi * np.cumsum(240 + 520 * spin) / SR) * 0.08
    return (fan * 0.6 + whine) * np.minimum(t / 0.4, 1) * np.minimum((length - t) / 0.8, 1)


def blips(length: float = 3.0) -> np.ndarray:
    out, t = np.zeros(int(SR * length)), 0.0
    while t < length - 0.1:
        f = rng.choice([1046.5, 1318.5, 1568, 2093])
        b = np.sin(2 * np.pi * f * ts(0.06)) * np.exp(-ts(0.06) * 50)
        i = int(t * SR)
        out[i : i + len(b)] += b[: len(out) - i] * rng.uniform(0.4, 1)
        t += rng.choice([0.12, 0.18, 0.24])
    return out


def scan(length: float = 1.0) -> np.ndarray:
    t = ts(length)
    return (np.sin(2 * np.pi * np.cumsum(600 + 900 * t / length) / SR) * 0.4 + bp(noise(length), 3000, 7000) * 0.3) * np.sin(np.pi * t / length)


def error() -> np.ndarray:
    t = ts(0.5)
    buzz = np.sign(np.sin(2 * np.pi * 110 * t)) * 0.4 + np.sin(2 * np.pi * 220 * t) * 0.3
    gate = ((t < 0.18) | ((t > 0.25) & (t < 0.45))).astype(float)
    return lp(buzz * gate, 1800)


def chaching() -> np.ndarray:
    t = ts(1.2)
    bell = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t * d) for f, a, d in ((2093, 1, 4), (2637, 0.6, 5), (3136, 0.4, 6), (4186, 0.2, 8)))
    out = np.zeros_like(t)
    i = int(0.08 * SR)
    out[i:] = bell[: len(t) - i] * 0.6
    rattle = bp(noise(0.25), 2000, 8000) * np.exp(-ts(0.25) * 18) * 0.6
    out[: len(rattle)] += rattle
    return out


def arpeggio(freqs: tuple[float, ...], gap: float, length: float) -> np.ndarray:
    out = np.zeros(int(SR * (length + gap * len(freqs))))
    for k, f in enumerate(freqs):
        t = ts(length)
        note = (np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * f * 3 * t) * np.exp(-t * 3)) * np.exp(-t * 3.5)
        i = int(k * gap * SR)
        out[i : i + len(note)] += note
    return out


if __name__ == "__main__":
    tl = json.loads((HERE / "src" / "timeline.json").read_text(encoding="utf-8"))
    clips = {c["id"]: c for c in tl["clips"]}
    save("music.wav", music(tl["total"], clips), peak=0.9)
    effects = {
        "whoosh": whoosh, "pop": pop, "tick": tick, "riser": riser, "impact": impact, "ding": ding,
        "typing": typing, "paper": paper, "stamp": stamp, "lock": lock, "hum": hum, "blips": blips,
        "scan": scan, "error": error, "chaching": chaching,
        "success": lambda: arpeggio((523.25, 659.25, 783.99, 1046.5), 0.09, 0.9),
        "chime": lambda: arpeggio((587.33, 880, 1174.66), 0.14, 1.3),
    }
    for name, fn in effects.items():
        save(f"sfx/{name}.wav", fn(), peak=0.9)
    print(f"music and {len(effects)} sound effects written to {OUT}")
