from __future__ import annotations

import json
from pathlib import Path


MODEL_VIEWER_CDN = "https://ajax.googleapis.com/ajax/libs/model-viewer/4.2.0/model-viewer.min.js"


def write_index_page(output_path: Path, manifest: list[dict[str, object]]) -> None:
    cards = []
    for entry in manifest:
        animated = is_animated(entry)
        parts = entry["parts"]
        eyebrow = "Animated AR model" if animated else "AR model"
        preview_behavior = 'autoplay animation-loop' if animated else 'auto-rotate rotation-per-second="8deg"'
        summary = (
            f"{entry['animation']['frameCount']} frames at {entry['animation']['fps']} fps"
            if animated
            else f"{len(parts)} mesh part{'s' if len(parts) != 1 else ''}"
        )
        cards.append(
            f"""
      <a class="card" href="{entry['page']}">
        <div class="card-preview">
          <model-viewer src="{viewer_glb(entry)}" ios-src="{entry['usdz']}" {preview_behavior} camera-orbit="45deg 70deg auto" disable-zoom disable-pan disable-tap interaction-prompt="none" pointer-events="none"></model-viewer>
        </div>
        <div class="card-copy">
          <span class="eyebrow">{eyebrow}</span>
          <h2>{entry['title']}</h2>
          <p>{summary}</p>
        </div>
      </a>
            """.strip()
        )

    output_path.write_text(
        f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Stanford CBCL AR Models</title>
  <script type="module" src="{MODEL_VIEWER_CDN}"></script>
  <style>
    :root {{
      --ink: #101820;
      --accent: #8c1515;
      --sky: #d7e9f8;
      --paper: #fbf7ef;
      --card: rgba(255,255,255,0.84);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Georgia, "Iowan Old Style", serif;
      background:
        radial-gradient(circle at top right, rgba(140, 21, 21, 0.16), transparent 30rem),
        linear-gradient(180deg, var(--paper), #f4f6f8 45%, var(--sky));
      color: var(--ink);
      min-height: 100vh;
    }}
    main {{
      width: min(1100px, calc(100vw - 2rem));
      margin: 0 auto;
      padding: 3rem 0 4rem;
    }}
    h1 {{
      font-size: clamp(2.6rem, 6vw, 4.8rem);
      line-height: 0.95;
      margin: 0;
      max-width: 12ch;
    }}
    .lede {{
      max-width: 48rem;
      font-size: 1.1rem;
      line-height: 1.6;
      margin: 1.25rem 0 2rem;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 280px));
      gap: 1rem;
      justify-content: start;
    }}
    .card {{
      text-decoration: none;
      color: inherit;
      background: var(--card);
      border: 1px solid rgba(16, 24, 32, 0.09);
      border-radius: 8px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      box-shadow: 0 18px 36px rgba(16, 24, 32, 0.08);
      transition: transform 180ms ease, box-shadow 180ms ease;
    }}
    .card:hover {{
      transform: translateY(-3px);
      box-shadow: 0 26px 44px rgba(16, 24, 32, 0.12);
    }}
    .card-preview {{
      aspect-ratio: 1 / 1;
      max-height: 280px;
      background:
        radial-gradient(circle at 50% 25%, rgba(140, 21, 21, 0.08), transparent 12rem),
        linear-gradient(180deg, #f7f0df, #edf4f8);
      border-bottom: 1px solid rgba(16, 24, 32, 0.09);
    }}
    .card-preview model-viewer {{
      width: 100%;
      height: 100%;
      pointer-events: none;
    }}
    .card-copy {{
      padding: 1rem;
      display: flex;
      flex-direction: column;
      justify-content: flex-end;
      gap: 0.45rem;
      flex: 1;
    }}
    .eyebrow {{
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 0.72rem;
      color: var(--accent);
    }}
    h2 {{
      margin: 0.5rem 0;
      font-size: 1.5rem;
    }}
    p {{ margin: 0; }}
  </style>
</head>
<body>
  <main>
    <span class="eyebrow">Stanford CBCL</span>
    <h1>Interactive AR models for scientific anatomy and simulation</h1>
    <p class="lede">Each entry opens a dedicated model page with Android and iOS AR support, direct asset downloads, and a downloadable QR code for sharing the exact page on mobile. Animated entries also expose cycle-aware pressure metadata in mmHg while keeping mobile AR downloads pinned to a representative static frame.</p>
    <section class="grid">
      {"".join(cards) if cards else '<p>No models have been published yet.</p>'}
    </section>
  </main>
</body>
</html>
"""
    )


def write_model_page(output_path: Path, entry: dict[str, object]) -> None:
    title = str(entry["title"])
    slug = str(entry["slug"])
    part_items = "".join(f"<li>{part}</li>" for part in entry["parts"])
    parameters = json.dumps(entry["blenderParameters"], indent=2)
    entry_payload = json.dumps(entry)
    animated = is_animated(entry)
    pressure = entry.get("pressurePresentation", {})
    pressure_range = pressure.get("rangeMmHg", [])
    color_range = pressure.get("colorRangeMmHg", pressure_range)
    viewer_behavior = "autoplay animation-loop" if animated else ""
    representative_name = ""
    if animated:
        representative_name = str(entry["animation"]["representativeFrame"]["sourceName"])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <script type="module" src="{MODEL_VIEWER_CDN}"></script>
  <style>
    :root {{
      --ink: #101820;
      --accent: #8c1515;
      --sand: #f7f0df;
      --panel: rgba(255, 255, 255, 0.9);
      --line: rgba(16, 24, 32, 0.12);
      --pressure-low: rgb(59, 76, 192);
      --pressure-mid: rgb(221, 221, 221);
      --pressure-high: rgb(180, 4, 38);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Georgia, "Iowan Old Style", serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(140, 21, 21, 0.18), transparent 28rem),
        linear-gradient(160deg, #fdf7ea, #edf1f4 56%, #dce7f0);
    }}
    main {{
      width: min(1180px, calc(100vw - 2rem));
      margin: 0 auto;
      padding: 1.5rem 0 3rem;
    }}
    .topbar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 1rem;
      margin-bottom: 1rem;
    }}
    .topbar a {{
      color: var(--accent);
      text-decoration: none;
      font-weight: 600;
    }}
    .hero {{
      display: grid;
      grid-template-columns: minmax(0, 1.5fr) minmax(280px, 0.9fr);
      gap: 1rem;
      align-items: stretch;
    }}
    .viewer,
    .meta {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 18px 40px rgba(16, 24, 32, 0.08);
    }}
    .viewer {{
      padding: 1rem;
    }}
    model-viewer {{
      width: 100%;
      min-height: 68vh;
      background:
        radial-gradient(circle at 50% 30%, rgba(140, 21, 21, 0.08), transparent 16rem),
        linear-gradient(180deg, var(--sand), #eff4f8);
      border-radius: 6px;
    }}
    .meta {{
      padding: 1rem;
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(2rem, 5vw, 3.5rem);
      line-height: 0.95;
    }}
    .actions {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0.75rem;
    }}
    .button {{
      appearance: none;
      border: 0;
      background: var(--accent);
      color: white;
      border-radius: 6px;
      padding: 0.8rem 0.95rem;
      font: inherit;
      cursor: pointer;
      text-align: center;
      text-decoration: none;
    }}
    .button.secondary {{
      background: white;
      color: var(--ink);
      border: 1px solid var(--line);
    }}
    .meta-card {{
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 0.85rem;
      background: rgba(255, 255, 255, 0.72);
    }}
    .meta-card h2 {{
      margin: 0 0 0.45rem;
      font-size: 1.05rem;
    }}
    .meta-card p {{
      margin: 0.2rem 0;
      line-height: 1.45;
    }}
    .legend-bar {{
      height: 14px;
      border-radius: 999px;
      background: linear-gradient(90deg, var(--pressure-low), var(--pressure-mid), var(--pressure-high));
      border: 1px solid var(--line);
      margin: 0.5rem 0;
    }}
    .legend-labels {{
      display: flex;
      justify-content: space-between;
      font-size: 0.86rem;
    }}
    .control-row {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 0.75rem;
      flex-wrap: wrap;
    }}
    .animation-panel {{
      display: grid;
      gap: 0.85rem;
      justify-items: center;
    }}
    .cycle-slider {{
      width: min(100%, 220px);
      aspect-ratio: 1;
      position: relative;
      display: grid;
      place-items: center;
      border: 0;
      padding: 0;
      background: transparent;
      color: inherit;
      cursor: pointer;
      touch-action: none;
      user-select: none;
      outline: none;
    }}
    .cycle-slider::before {{
      content: "";
      position: absolute;
      inset: 12%;
      border-radius: 999px;
      background: radial-gradient(circle at center, rgba(255, 255, 255, 0.92), rgba(255, 255, 255, 0.36));
      box-shadow: inset 0 0 0 1px rgba(16, 24, 32, 0.05);
    }}
    .cycle-slider:hover .cycle-slider-knob,
    .cycle-slider:focus-visible .cycle-slider-knob,
    .cycle-slider.is-dragging .cycle-slider-knob {{
      transform: scale(1.08);
    }}
    .cycle-slider:focus-visible {{
      box-shadow: 0 0 0 4px rgba(140, 21, 21, 0.18);
      border-radius: 999px;
    }}
    .cycle-slider.is-dragging {{
      cursor: grabbing;
    }}
    .cycle-slider-svg {{
      width: 100%;
      height: 100%;
      overflow: visible;
      position: relative;
      z-index: 1;
    }}
    .cycle-slider-track,
    .cycle-slider-progress,
    .cycle-slider-hit {{
      fill: none;
      cx: 80;
      cy: 80;
      r: 60;
    }}
    .cycle-slider-track {{
      stroke: rgba(16, 24, 32, 0.12);
      stroke-width: 10;
    }}
    .cycle-slider-progress {{
      stroke: var(--accent);
      stroke-width: 10;
      stroke-linecap: round;
      transform: rotate(-90deg);
      transform-origin: 80px 80px;
      transition: stroke-dashoffset 120ms linear;
    }}
    .cycle-slider-hit {{
      stroke: transparent;
      stroke-width: 26;
      cursor: pointer;
    }}
    .cycle-slider-knob {{
      fill: var(--accent);
      stroke: white;
      stroke-width: 4;
      transition: transform 140ms ease;
      transform-origin: center;
    }}
    .cycle-slider-label {{
      position: absolute;
      inset: 0;
      display: grid;
      place-items: center;
      padding: 3rem;
      text-align: center;
      font-size: 1rem;
      line-height: 1.15;
      font-weight: 600;
      z-index: 2;
      pointer-events: none;
    }}
    .cycle-slider-note {{
      text-align: center;
    }}
    ul {{
      margin: 0;
      padding-left: 1.15rem;
      columns: 2;
    }}
    pre {{
      margin: 0;
      padding: 0.75rem;
      border-radius: 6px;
      background: #f3efe7;
      font-size: 0.84rem;
      overflow: auto;
    }}
    #qr-preview {{
      width: min(100%, 220px);
      aspect-ratio: 1;
      border-radius: 6px;
      border: 1px solid var(--line);
      background: white;
      object-fit: contain;
    }}
    .eyebrow {{
      margin: 0;
      color: var(--accent);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 0.72rem;
    }}
    @media (max-width: 900px) {{
      .hero {{
        grid-template-columns: 1fr;
      }}
      model-viewer {{
        min-height: 54vh;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <div class="topbar">
      <a href="../../">All models</a>
      <span>Stanford CBCL AR</span>
    </div>
    <section class="hero">
      <div class="viewer">
        <model-viewer id="model-viewer" src="../../{viewer_glb(entry)}" ios-src="../../{entry['usdz']}" ar ar-modes="webxr scene-viewer quick-look" ar-scale="auto" camera-controls shadow-intensity="1" {viewer_behavior}></model-viewer>
      </div>
      <aside class="meta">
        <div>
          <p class="eyebrow">Dedicated model page</p>
          <h1>{title}</h1>
        </div>
        <div class="actions">
          <a class="button" href="../../{download_glb(entry)}" download>Download GLB</a>
          <a class="button secondary" href="../../{entry['usdz']}" download>Download USDZ</a>
          <button class="button" id="download-qr" type="button">Download QR code</button>
          <a class="button secondary" href="../../{viewer_glb(entry)}">Open viewer asset</a>
        </div>
        {"".join(animated_meta_cards(entry, pressure_range, color_range, representative_name))}
        <div class="meta-card">
          <h2>Mesh parts</h2>
          <ul>{part_items}</ul>
        </div>
        <div class="meta-card">
          <h2>QR preview</h2>
          <img id="qr-preview" alt="QR code preview">
        </div>
        <div class="meta-card">
          <h2>Blender parameters</h2>
          <pre>{parameters}</pre>
        </div>
      </aside>
    </section>
  </main>
  <script>
    const entry = {entry_payload};
    const qrPreview = document.getElementById("qr-preview");
    const qrButton = document.getElementById("download-qr");
    const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=720x720&data=${{encodeURIComponent(window.location.href)}}`;
    qrPreview.src = qrUrl;
    qrButton.addEventListener("click", async () => {{
      const response = await fetch(qrUrl);
      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = "{slug}-qr.png";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(objectUrl);
    }});

    if (entry.animation && entry.pressurePresentation) {{
      const viewer = document.getElementById("model-viewer");
      const toggleButton = document.getElementById("toggle-play");
      const slider = document.getElementById("cycle-slider");
      const cycleLabel = document.getElementById("cycle-label");
      const progressRing = document.getElementById("cycle-progress");
      const knob = document.getElementById("cycle-knob");
      const frames = entry.pressurePresentation.sampledFrames || [];
      const fallbackDuration = Number(entry.animation.durationSeconds || 0);
      const sliderRadius = 60;
      const sliderCenter = 80;
      const circumference = 2 * Math.PI * sliderRadius;
      const frameStep = frames.length > 1 ? 1 / (frames.length - 1) : 1;
      let isScrubbing = false;
      let wasPlayingBeforeScrub = false;
      let currentProgress = 0;

      progressRing.style.strokeDasharray = `${{circumference}}`;
      progressRing.style.strokeDashoffset = `${{circumference}}`;

      const frameAtProgress = (progress) => {{
        if (!frames.length) return null;
        const clamped = Math.max(0, Math.min(1, progress));
        const frameIndex = Math.min(frames.length - 1, Math.round(clamped * (frames.length - 1)));
        return frames[frameIndex];
      }};

      const normalizeProgress = (progress) => Math.max(0, Math.min(1, progress));

      const updateSliderVisuals = (progress) => {{
        const clamped = normalizeProgress(progress);
        currentProgress = clamped;
        progressRing.style.strokeDashoffset = `${{circumference * (1 - clamped)}}`;
        const angle = clamped * Math.PI * 2 - Math.PI / 2;
        const x = sliderCenter + sliderRadius * Math.cos(angle);
        const y = sliderCenter + sliderRadius * Math.sin(angle);
        knob.setAttribute("cx", x.toFixed(3));
        knob.setAttribute("cy", y.toFixed(3));
        const frame = frameAtProgress(progress);
        if (frame) {{
          cycleLabel.textContent = frame.label;
          const percent = Math.round(clamped * 100);
          slider.setAttribute("aria-valuenow", String(percent));
          slider.setAttribute("aria-valuetext", frame.label);
        }} else {{
          const percent = Math.round(clamped * 100);
          cycleLabel.textContent = `${{percent}}% of cycle`;
          slider.setAttribute("aria-valuenow", String(percent));
          slider.setAttribute("aria-valuetext", `${{percent}}% of cycle`);
        }}
      }};

      const viewerDuration = () => Number(viewer.duration || fallbackDuration || 0);

      const syncViewerTime = (progress) => {{
        const duration = viewerDuration();
        if (duration > 0) {{
          viewer.currentTime = normalizeProgress(progress) * duration;
        }}
      }};

      const setPausedUi = () => {{
        toggleButton.textContent = "Play animation";
      }};

      const setPlayingUi = () => {{
        toggleButton.textContent = "Pause animation";
      }};

      const setProgress = (progress, syncViewer = true) => {{
        const clamped = normalizeProgress(progress);
        if (syncViewer) {{
          syncViewerTime(clamped);
        }}
        updateSliderVisuals(clamped);
      }};

      const progressFromPointer = (event) => {{
        const rect = slider.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        let angle = Math.atan2(event.clientY - centerY, event.clientX - centerX) + Math.PI / 2;
        if (angle < 0) {{
          angle += Math.PI * 2;
        }}
        return angle / (Math.PI * 2);
      }};

      const beginScrub = (event) => {{
        wasPlayingBeforeScrub = !viewer.paused;
        viewer.pause();
        setPausedUi();
        isScrubbing = true;
        slider.classList.add("is-dragging");
        slider.setPointerCapture(event.pointerId);
        setProgress(progressFromPointer(event));
      }};

      const updateAnimationState = () => {{
        const duration = viewerDuration();
        const currentTime = Number(viewer.currentTime || 0);
        let progress = 0;
        if (duration > 0) {{
          const rawProgress = currentTime / duration;
          progress = viewer.paused ? Math.min(rawProgress, 1) : rawProgress % 1;
        }}
        if (!isScrubbing) {{
          updateSliderVisuals(progress);
        }}
        requestAnimationFrame(updateAnimationState);
      }};

      viewer.addEventListener("load", () => {{
        if (viewer.availableAnimations && viewer.availableAnimations.length > 0) {{
          viewer.animationName = viewer.availableAnimations[0];
        }}
        setProgress(0, false);
        viewer.play();
        setPlayingUi();
      }});

      viewer.addEventListener("finished", () => {{
        viewer.currentTime = 0;
        viewer.play();
        setPlayingUi();
      }});

      toggleButton.addEventListener("click", () => {{
        if (viewer.paused) {{
          viewer.play();
          setPlayingUi();
        }} else {{
          viewer.pause();
          setPausedUi();
        }}
      }});

      slider.addEventListener("pointerdown", (event) => {{
        event.preventDefault();
        beginScrub(event);
      }});

      slider.addEventListener("pointermove", (event) => {{
        if (!isScrubbing) {{
          return;
        }}
        setProgress(progressFromPointer(event));
      }});

      slider.addEventListener("pointerup", (event) => {{
        if (!isScrubbing) {{
          return;
        }}
        isScrubbing = false;
        slider.classList.remove("is-dragging");
        slider.releasePointerCapture(event.pointerId);
        if (wasPlayingBeforeScrub) {{
          wasPlayingBeforeScrub = false;
        }}
        viewer.pause();
        setPausedUi();
      }});

      slider.addEventListener("pointercancel", (event) => {{
        if (!isScrubbing) {{
          return;
        }}
        isScrubbing = false;
        slider.classList.remove("is-dragging");
        slider.releasePointerCapture(event.pointerId);
        viewer.pause();
        setPausedUi();
      }});

      slider.addEventListener("keydown", (event) => {{
        let nextProgress = null;
        if (event.key === "ArrowLeft" || event.key === "ArrowDown") {{
          nextProgress = currentProgress - frameStep;
        }} else if (event.key === "ArrowRight" || event.key === "ArrowUp") {{
          nextProgress = currentProgress + frameStep;
        }} else if (event.key === "Home") {{
          nextProgress = 0;
        }} else if (event.key === "End") {{
          nextProgress = 1;
        }}
        if (nextProgress === null) {{
          return;
        }}
        event.preventDefault();
        viewer.pause();
        setPausedUi();
        setProgress(nextProgress);
      }});

      requestAnimationFrame(updateAnimationState);
    }}
  </script>
</body>
</html>
"""
    )


def animated_meta_cards(
    entry: dict[str, object],
    pressure_range: list[object],
    color_range: list[object],
    representative_name: str,
) -> list[str]:
    if not is_animated(entry):
        return []

    animation = entry["animation"]
    pressure = entry["pressurePresentation"]
    return [
        f"""
        <div class="meta-card">
          <h2>Animation</h2>
          <div class="animation-panel">
            <div
              class="cycle-slider"
              id="cycle-slider"
              role="slider"
              tabindex="0"
              aria-label="Cardiac cycle position"
              aria-valuemin="0"
              aria-valuemax="100"
              aria-valuenow="0"
              aria-valuetext="0% of cycle"
            >
              <svg class="cycle-slider-svg" id="cycle-slider-svg" viewBox="0 0 160 160" aria-hidden="true">
                <circle class="cycle-slider-track" cx="80" cy="80" r="60"></circle>
                <circle class="cycle-slider-progress" id="cycle-progress" cx="80" cy="80" r="60"></circle>
                <circle class="cycle-slider-hit" cx="80" cy="80" r="60"></circle>
                <circle class="cycle-slider-knob" id="cycle-knob" cx="80" cy="20" r="9"></circle>
              </svg>
              <div class="cycle-slider-label" id="cycle-label">0% of cycle</div>
            </div>
            <div class="control-row">
              <button class="button secondary" id="toggle-play" type="button">Pause animation</button>
            </div>
          </div>
          <p class="cycle-slider-note">{animation['frameCount']} sampled frames at {animation['fps']} fps.</p>
        </div>
        """.strip(),
        f"""
        <div class="meta-card">
          <h2>Pressure Presentation</h2>
          <div class="legend-bar"></div>
          <div class="legend-labels">
            <span>{format_range_label(color_range, 0)} {pressure['unit']}</span>
            <span>{format_range_label(color_range, 1)} {pressure['unit']}</span>
          </div>
          <p>Static GLB and USDZ downloads use the systolic pressure result.</p>
        </div>
        """.strip(),
    ]


def format_range_label(values: list[object], index: int) -> str:
    if len(values) <= index:
        return "--"
    return f"{float(values[index]):.1f}"


def is_animated(entry: dict[str, object]) -> bool:
    animation = entry.get("animation")
    return isinstance(animation, dict) and bool(animation.get("enabled"))


def viewer_glb(entry: dict[str, object]) -> str:
    return str(entry["glb"])


def download_glb(entry: dict[str, object]) -> str:
    return str(entry.get("downloadGlb", entry["glb"]))
