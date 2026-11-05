# X-TREATS · demo video generator

Produces a narrated guided tour of the web-en interface: `out/x-treats-demo.mp4` (1920×1080, ~3 min)
and `out/x-treats-demo.srt` (subtitles). Everything happens inside `web-en/demo/`; outputs are git-ignored.

```powershell
powershell -File web-en\demo\make_demo.ps1               # v2 (default): out/x-treats-demo-v2.mp4, ~3:29
powershell -File web-en\demo\make_demo.ps1 -Version v1   # v1: out/x-treats-demo.mp4, ~3:04
```

The server must be running on :5051 with no active run. Each version has its own script
(`scenes.json` / `scenes_v2.json`), working folder (`build/` / `build/v2/`) and output file, so versions never
overwrite each other. v2 drops the institutions scene and adds the Advanced options, the per-increment time
breakdown, the table view and the run history; its cursor moves in sync with each narrated sentence.
Output: H.264 (High) + AAC, 1920×1080, 30 fps.

| Step | File | What it does |
|---|---|---|
| 1 | `scenes.json` + `tts.py` | The script (one narration text per scene) → neural voice per scene (`edge-tts`, voice `en-US-AndrewNeural`), plus sentence timings for captions. Only the narration text is sent to the speech service. |
| 2 | `record_demo.js` | Drives the real UI in headless Chrome (DevTools Protocol): animated cursor, on-screen captions, title cards. Starts a **real run** (Amazon-Google · X-TREATS+LEMON · 200 pairs · τ = 15 s · 3 increments); waits are recorded as fast-forward segments. |
| 3 | `assemble.py` | Compresses the waits (6×), places each narration clip at the start of its scene, encodes H.264/AAC with the bundled ffmpeg (`imageio-ffmpeg`), writes the `.srt`. |

To change what is said, edit `scenes.json`; to change what is shown or the timing, edit the
scene actions at the end of `record_demo.js`, then run the script again.

Notes: the recording adds one run to "Previous runs" (delete `web-en/runtime/runs/<id>` if unwanted;
its id is printed and saved in `build/timeline.json`), and Ditto appends one line to the repository's `log.txt`.
