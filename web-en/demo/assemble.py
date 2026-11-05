"""Step 3 — build the MP4 (Python 3.7 + numpy + imageio-ffmpeg).

    python assemble.py [--keep-frames]   -> out/x-treats-demo.mp4 + out/x-treats-demo.srt

Fast-forward segments recorded by record_demo.js are compressed by their speed
factor; each scene's narration is placed at the (compressed) start of its scene.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import wave

import imageio_ffmpeg
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
VERSION = os.environ.get("DEMO_VERSION", "v1")  # v1 → build/, x-treats-demo.mp4 ; vN → build/vN/, x-treats-demo-vN.mp4
BUILD = os.path.join(HERE, "build") if VERSION == "v1" else os.path.join(HERE, "build", VERSION)
NAME = "x-treats-demo" if VERSION == "v1" else "x-treats-demo-" + VERSION
OUT = os.path.join(HERE, "out")
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
RATE = 44100


def load(name):
    with open(os.path.join(BUILD, name), encoding="utf-8") as fh:
        return json.load(fh)


def make_clock(ff):
    """Real time (s) -> video time (s), compressing fast-forward segments."""
    ff = sorted(ff, key=lambda s: s["start"])

    def v(t):
        out = t
        for s in ff:
            if t > s["start"]:
                out -= (min(t, s["end"]) - s["start"]) * (1 - 1 / s["speed"])
        return out
    return v


def split_caption(c):  # same rule as record_demo.js
    if len(c["text"]) <= 105:
        return [c]
    parts, chunks, buf = re.split(r"(?<=[,:;])\s+", c["text"]), [], ""
    for p in parts:
        if buf and len(buf + " " + p) > 95:
            chunks.append(buf)
            buf = p
        else:
            buf = buf + " " + p if buf else p
    if buf:
        chunks.append(buf)
    total, t, out = sum(len(s) for s in chunks), c["start"], []
    for s in chunks:
        d = (c["end"] - c["start"]) * len(s) / total
        out.append({"start": t, "end": t + d, "text": s})
        t += d
    return out


def srt_time(x):
    ms = int(round(x * 1000))
    return "%02d:%02d:%02d,%03d" % (ms // 3600000, ms // 60000 % 60, ms // 1000 % 60, ms % 1000)


def decode(mp3):
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", mp3, "-f", "s16le", "-ac", "1", "-ar", str(RATE), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32)


def main():
    tl, nar = load("timeline.json"), load("narration.json")
    clock = make_clock(tl["ff"])
    base = clock(tl["frames"][0]["t"])  # the video starts at the first captured frame
    v = lambda t: clock(t) - base
    total = v(tl["end"])
    os.makedirs(OUT, exist_ok=True)

    # video: variable-duration frames via the concat demuxer
    frames = tl["frames"]
    lst = os.path.join(BUILD, "frames.txt")
    fdir = os.path.join(BUILD, "frames").replace("\\", "/")  # absolute: ffmpeg 4.2 mis-resolves relative entries
    with open(lst, "w", encoding="utf-8") as fh:
        for i, f in enumerate(frames):
            nxt = v(frames[i + 1]["t"]) if i + 1 < len(frames) else total
            dur = max(0.0, nxt - v(f["t"]))
            fh.write("file '%s/%s'\nduration %.4f\n" % (fdir, f["file"], dur))
        fh.write("file '%s/%s'\n" % (fdir, frames[-1]["file"]))

    # audio: each scene's narration at its compressed start time
    track = np.zeros(int((total + 1) * RATE), dtype=np.float32)
    srt, k = [], 1
    by_id = {s["id"]: s for s in nar["scenes"]}
    for sc in tl["scenes"]:
        start = v(sc["start"])
        pcm = decode(os.path.join(BUILD, "audio", sc["id"] + ".mp3"))
        a = int(start * RATE)
        track[a:a + len(pcm)] += pcm[: max(0, len(track) - a)]
        for c in (x for cap in by_id[sc["id"]]["captions"] for x in split_caption(cap)):
            srt.append("%d\n%s --> %s\n%s\n" % (k, srt_time(start + c["start"]), srt_time(start + c["end"]), c["text"]))
            k += 1
    peak = np.abs(track).max() or 1.0
    track = np.clip(track * min(1.0, 30000 / peak), -32768, 32767).astype(np.int16)
    wav = os.path.join(BUILD, "narration.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(track.tobytes())

    mp4 = os.path.join(OUT, NAME + ".mp4")
    subprocess.run([FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-i", wav,
                    "-vf", "fps=30,scale=1920:1080:flags=lanczos,format=yuv420p",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                    "-c:a", "aac", "-b:a", "160k", "-t", "%.3f" % total, "-movflags", "+faststart", mp4], check=True)
    with open(os.path.join(OUT, NAME + ".srt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(srt))
    print("video: %s (%.1f s, %.1f MB) · %d frames · %d fast-forward segment(s)"
          % (mp4, total, os.path.getsize(mp4) / 1e6, len(frames), len(tl["ff"])))
    if "--keep-frames" not in sys.argv:
        shutil.rmtree(os.path.join(BUILD, "frames"), ignore_errors=True)


if __name__ == "__main__":
    main()
