"""Step 1 — synthesize the narration (needs Python >= 3.8 with `edge-tts`).

    python tts.py            -> build/audio/<scene>.mp3 + build/narration.json

narration.json holds, per scene, the audio duration and the start/end of every
sentence (from the service's sentence boundaries), used for the on-screen captions.
Only the narration text is sent to the speech service.
"""
import asyncio
import json
import os
import re
import subprocess
import sys

import edge_tts

HERE = os.path.dirname(os.path.abspath(__file__))
VERSION = os.environ.get("DEMO_VERSION", "v1")  # v1: scenes.json -> build/ ; vN: scenes_vN.json -> build/vN/
SCENES = os.path.join(HERE, "scenes.json" if VERSION == "v1" else "scenes_%s.json" % VERSION)
BUILD = os.path.join(HERE, "build") if VERSION == "v1" else os.path.join(HERE, "build", VERSION)
AUDIO = os.path.join(BUILD, "audio")
FFMPEG = os.environ.get("FFMPEG", "ffmpeg")


def duration(path):
    out = subprocess.run([FFMPEG, "-hide_banner", "-i", path], capture_output=True, text=True).stderr
    h, m, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out).groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


async def synth(scene, voice, rate):
    path = os.path.join(AUDIO, scene["id"] + ".mp3")
    sentences = []
    comm = edge_tts.Communicate(scene["text"], voice, rate=rate)
    with open(path, "wb") as fh:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                fh.write(chunk["data"])
            elif chunk["type"] in ("SentenceBoundary", "WordBoundary"):
                start = chunk["offset"] / 1e7
                sentences.append({"kind": chunk["type"], "start": start, "end": start + chunk["duration"] / 1e7, "text": chunk["text"]})
    dur = duration(path)
    caps = [s for s in sentences if s["kind"] == "SentenceBoundary"]
    if not caps:  # fall back to splitting the text proportionally to its length
        parts = [p.strip() for p in re.split(r"(?<=[.!?:])\s+", scene["text"]) if p.strip()]
        total, t = sum(len(p) for p in parts), 0.0
        for p in parts:
            d = dur * len(p) / total
            caps.append({"start": t, "end": t + d, "text": p})
            t += d
    return {"id": scene["id"], "duration": dur, "captions": [{"start": c["start"], "end": c["end"], "text": c["text"]} for c in caps]}


async def main():
    with open(SCENES, encoding="utf-8") as fh:
        cfg = json.load(fh)
    os.makedirs(AUDIO, exist_ok=True)
    out = []
    for sc in cfg["scenes"]:
        for attempt in range(5):  # the service fails intermittently ("No audio was received")
            try:
                res = await synth(sc, cfg["voice"], cfg.get("rate", "+0%"))
                break
            except edge_tts.exceptions.NoAudioReceived:
                if attempt == 4:
                    raise
                await asyncio.sleep(2 * (attempt + 1))
        print("%-9s %5.1f s  %d captions" % (res["id"], res["duration"], len(res["captions"])))
        out.append(res)
    with open(os.path.join(BUILD, "narration.json"), "w", encoding="utf-8") as fh:
        json.dump({"voice": cfg["voice"], "scenes": out}, fh, indent=2, ensure_ascii=False)
    print("total narration: %.1f s" % sum(s["duration"] for s in out))


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
