from __future__ import annotations

import json
from pathlib import Path


MODEL_VIEWER_CDN = "https://ajax.googleapis.com/ajax/libs/model-viewer/3.1.1/model-viewer.min.js"


def write_index_page(output_path: Path, manifest: list[dict[str, object]]) -> None:
    cards = []
    for entry in manifest:
        cards.append(
            f"""
      <a class="card" href="{entry['page']}">
        <div class="card-preview">
          <model-viewer src="{entry['glb']}" ios-src="{entry['usdz']}" auto-rotate rotation-per-second="8deg" camera-orbit="45deg 70deg auto" disable-zoom disable-pan disable-tap interaction-prompt="none" pointer-events="none"></model-viewer>
        </div>
        <div class="card-copy">
          <span class="eyebrow">AR model</span>
          <h2>{entry['title']}</h2>
          <p>{len(entry['parts'])} mesh part{'s' if len(entry['parts']) != 1 else ''}</p>
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
    <p class="lede">Each entry opens a dedicated model page with Android and iOS AR support, direct asset downloads, and a downloadable QR code for sharing the exact page on mobile. The home page now includes a live preview so visitors can spot the right model before they click through.</p>
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
        <model-viewer src="../../{entry['glb']}" ios-src="../../{entry['usdz']}" ar ar-modes="webxr scene-viewer quick-look" ar-scale="auto" camera-controls shadow-intensity="1"></model-viewer>
      </div>
      <aside class="meta">
        <div>
          <p style="margin:0;color:var(--accent);text-transform:uppercase;letter-spacing:0.08em;font-size:0.72rem;">Dedicated model page</p>
          <h1>{title}</h1>
        </div>
        <div class="actions">
          <a class="button" href="../../{entry['glb']}" download>Download GLB</a>
          <a class="button secondary" href="../../{entry['usdz']}" download>Download USDZ</a>
          <button class="button" id="download-qr" type="button">Download QR code</button>
          <a class="button secondary" href="../../{entry['glb']}">Open asset path</a>
        </div>
        <div>
          <h2 style="margin:0 0 0.5rem;font-size:1.15rem;">Mesh parts</h2>
          <ul>{part_items}</ul>
        </div>
        <div>
          <h2 style="margin:0 0 0.5rem;font-size:1.15rem;">QR preview</h2>
          <img id="qr-preview" alt="QR code preview">
        </div>
        <div>
          <h2 style="margin:0 0 0.5rem;font-size:1.15rem;">Blender parameters</h2>
          <pre>{parameters}</pre>
        </div>
      </aside>
    </section>
  </main>
  <script>
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
  </script>
</body>
</html>
"""
    )
