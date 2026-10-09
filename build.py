#!/usr/bin/env python3
"""Build a single self-contained HTML workout file.

For every exercise it locates the animated demonstration GIF on fitcron.com
(via the page's og:image), downloads it, transcodes it to a small animated
WebP with ffmpeg, and embeds it as a base64 data URI inside the output HTML.

The result (rutina-franco.html) works fully offline on a phone.

Usage:
    python build.py
"""

from __future__ import annotations

import base64
import json
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
OUTPUT = ROOT / "rutina-franco.html"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) rutina-franco-builder/1.0"
WEBP_WIDTH = 360
WEBP_QUALITY = 60

# ---------------------------------------------------------------------------
# Routine definition. `slug` is the fitcron.com/exercise/<slug> identifier.
# ---------------------------------------------------------------------------
ROUTINE = {
    "title": "Rutina de Hipertrofia",
    "subtitle": "4 días/semana · Torso / Piernas",
    "days": [
        {
            "id": "lunes",
            "label": "Lunes",
            "focus": "Torso A",
            "exercises": [
                {
                    "name": "Press inclinado con barra o máquina",
                    "scheme": "3 × 8-12",
                    "cue": "Banco inclinado a unos 30°. Elegí la variante más cómoda y disponible.",
                    "slug": "press-inclinado-con-barra-pectoral",
                },
                {
                    "name": "Aperturas en máquina (pec deck)",
                    "scheme": "3 × 12-15",
                    "cue": "Misma máquina que el posterior de hombro. Codos ligeramente flexionados y fijos; buscá el estiramiento del pecho y hacé una pausa breve al juntar.",
                    "slug": "aperturas-en-maquina-pectoral",
                },
                {
                    "name": "Jalón al pecho (agarre pronado medio-amplio)",
                    "scheme": "3 × 8-12",
                    "cue": "Palmas hacia adelante y codos dirigidos hacia abajo.",
                    "slug": "jalon-en-pronacion-en-polea-alta-dorsal",
                },
                {
                    "name": "Remo sentado en polea (agarre cerrado neutro)",
                    "scheme": "3 × 8-12",
                    "cue": "Usar el agarre en V, con las palmas enfrentadas. Evitar balancear el torso.",
                    "slug": "remo-horizontal-cerrado-neutro-en-polea-dorsal",
                },
                {
                    "name": "Elevaciones laterales con mancuernas",
                    "scheme": "3 × 12-15",
                    "cue": "Elevar los brazos hacia los lados sin impulso ni encoger los hombros.",
                    "slug": "elevaciones-laterales-neutras-con-mancuernas-deltoides",
                },
                {
                    "name": "Curl de bíceps alternado con mancuernas",
                    "scheme": "3 × 10-12 (por brazo)",
                    "cue": "Girar la palma hacia arriba al flexionar el codo; evitar balancear la espalda.",
                    "slug": "curl-con-giro-alterno-con-mancuernas-biceps",
                },
                {
                    "name": "Extensión de tríceps en polea con cuerda",
                    "scheme": "3 × 10-15",
                    "cue": "Mantener los codos cerca del cuerpo y separar ligeramente los extremos de la cuerda al extender.",
                    "slug": "extension-vertical-neutro-en-polea-alta-triceps",
                },
            ],
        },
        {
            "id": "martes",
            "label": "Martes",
            "focus": "Piernas A + Abdominales",
            "exercises": [
                {
                    "name": "Prensa de piernas a 45°",
                    "scheme": "4 × 8-12",
                    "cue": "Pies al ancho de hombros; mantener la pelvis apoyada durante todo el recorrido.",
                    "slug": "prensa-inclinada-pierna",
                },
                {
                    "name": "Extensión de cuádriceps en máquina",
                    "scheme": "3 × 10-15",
                    "cue": "Extender las rodillas de forma controlada, sin dar impulso.",
                    "slug": "extension-de-cuadriceps-en-maquina-pierna",
                },
                {
                    "name": "Curl femoral sentado en máquina",
                    "scheme": "3 × 10-15",
                    "cue": "Controlar tanto la flexión como el regreso del peso.",
                    "slug": "curl-femoral-vertical-en-maquina-pierna",
                },
                {
                    "name": "Elevación de gemelos de pie en máquina",
                    "scheme": "3 × 12-20",
                    "cue": "Recorrido completo, pausa breve arriba y estiramiento controlado abajo.",
                    "slug": "extension-de-gemelos-en-maquina-con-carga-superior-pierna",
                },
                {
                    "name": "Crunch abdominal en máquina",
                    "scheme": "3 × 12-20",
                    "cue": "Máquina sentado con chest pad. Flexioná el tronco contrayendo el abdomen (hacete 'bolita') sin tirar con los brazos ni con el cuello.",
                    "slug": "crunch-superior-vertical-en-maquina-abdomen",
                },
            ],
        },
        {
            "id": "jueves",
            "label": "Jueves",
            "focus": "Torso B",
            "exercises": [
                {
                    "name": "Press plano con barra o máquina",
                    "scheme": "3 × 8-12",
                    "cue": "Elegí barra o máquina de press horizontal según disponibilidad y comodidad.",
                    "slug": "press-banca-con-barra-pectoral",
                },
                {
                    "name": "Jalón al pecho (agarre supino o neutro cerrado)",
                    "scheme": "3 × 8-12",
                    "cue": "Supino: palmas hacia vos con barra compatible. Neutro: palmas enfrentadas con agarre paralelo o en V.",
                    "slug": "jalon-en-supinacion-en-polea-alta-dorsal",
                },
                {
                    "name": "Remo en máquina, pecho apoyado (agarre medio)",
                    "scheme": "3 × 8-12",
                    "cue": "Mantener el pecho apoyado y evitar impulsarte con el torso.",
                    "slug": "remo-horizontal-neutro-en-maquina-dorsal",
                },
                {
                    "name": "Press de hombros en máquina de carga con discos",
                    "scheme": "3 × 8-12",
                    "cue": "Máquina de palancas cargada con discos. Ajustá el asiento para que las asas queden a la altura de los hombros.",
                    "slug": "press-militar-neutro-en-maquina-deltoides",
                },
                {
                    "name": "Pájaros en máquina (posterior de hombro)",
                    "scheme": "3 × 12-15",
                    "cue": "Sentado al revés en la máquina de aperturas, pecho apoyado. Empujá con los codos, no con las manos, y no encojas los trapecios.",
                    "slug": "aperturas-traseras-en-pronacion-en-maquina-deltoides",
                },
                {
                    "name": "Curl de bíceps con barra W (EZ)",
                    "scheme": "3 × 10-12",
                    "cue": "Usar las secciones anguladas de la barra, con muñecas cómodas y codos estables.",
                    "slug": "curl-en-supinacion-con-barra-z-biceps",
                },
                {
                    "name": "Extensión de tríceps sobre la cabeza con cuerda",
                    "scheme": "3 × 10-15",
                    "cue": "Mantener los codos estables y evitar arquear excesivamente la espalda.",
                    "slug": "extension-vertical-neutra-en-polea-baja-triceps",
                },
            ],
        },
        {
            "id": "viernes",
            "label": "Viernes",
            "focus": "Piernas B + Abdominales",
            "exercises": [
                {
                    "name": "Hack squat en máquina",
                    "scheme": "3 × 8-12",
                    "cue": "Si no hay máquina, usar prensa de piernas.",
                    "slug": "sentadilla-inclinada-cerrada-en-maquina-pierna",
                },
                {
                    "name": "Extensión de cuádriceps en máquina",
                    "scheme": "3 × 10-15",
                    "cue": "Controlar el movimiento durante todo el recorrido.",
                    "slug": "extension-de-cuadriceps-en-maquina-pierna",
                },
                {
                    "name": "Curl femoral tumbado en máquina",
                    "scheme": "3 × 10-15",
                    "cue": "Realizar la flexión y el regreso del peso de forma controlada.",
                    "slug": "curl-femoral-horizontal-en-maquina-pierna",
                },
                {
                    "name": "Elevación de gemelos sentado en máquina",
                    "scheme": "3 × 12-20",
                    "cue": "Hacer una pausa breve arriba y evitar rebotes.",
                    "slug": "extension-de-gemelos-sentado-en-maquina-pierna",
                },
                {
                    "name": "Crunch abdominal en máquina",
                    "scheme": "3 × 12-20",
                    "cue": "Máquina sentado con chest pad. Flexioná el tronco contrayendo el abdomen (hacete 'bolita') sin tirar con los brazos ni con el cuello.",
                    "slug": "crunch-superior-vertical-en-maquina-abdomen",
                },
            ],
        },
    ],
    "notes": [
        ("Descanso", "2-3 minutos en ejercicios compuestos; 60-120 segundos en aislamientos."),
        ("Intensidad", "Terminar la mayoría de las series con 1-3 repeticiones en reserva."),
        ("Progresión", "Cuando completes todas las series en el extremo superior del rango con buena técnica, aumentá ligeramente el peso."),
        ("Distribución", "Miércoles, sábado y domingo: descanso o actividad ligera."),
    ],
    "note_footer": "Nota: la prensa y la hack squat también involucran los glúteos aunque no se realicen ejercicios específicos para ese músculo.",
}


def fetch(url: str) -> bytes:
    safe_url = urllib.parse.quote(url, safe=":/?&=#%+@[]()!$',;~")
    req = urllib.request.Request(safe_url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def gif_url_for_slug(slug: str) -> str:
    """Return the full-size animated GIF URL advertised by an exercise page."""
    if not slug:
        return ""
    page = fetch(f"https://fitcron.com/exercise/{slug}/").decode("utf-8", "replace")
    match = re.search(r'og:image"\s+content="([^"]+)"', page)
    if not match:
        raise RuntimeError(f"No og:image found for slug '{slug}'")
    return match.group(1)


def build_webp(slug: str, gif_url: str) -> bytes:
    """Download the GIF and transcode it to a small animated WebP."""
    ASSETS.mkdir(exist_ok=True)
    gif_path = ASSETS / f"{slug}.gif"
    webp_path = ASSETS / f"{slug}.webp"

    if not gif_path.exists():
        gif_path.write_bytes(fetch(gif_url))
    if not webp_path.exists():
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error",
                "-i", str(gif_path),
                "-vf", f"scale={WEBP_WIDTH}:-1:flags=lanczos",
                "-c:v", "libwebp", "-lossless", "0", "-q:v", str(WEBP_QUALITY),
                "-loop", "0", "-an",
                str(webp_path),
            ],
            check=True,
        )
    return webp_path.read_bytes()


def to_data_uri(webp_bytes: bytes) -> str:
    return "data:image/webp;base64," + base64.b64encode(webp_bytes).decode("ascii")


def build_media() -> dict[str, str]:
    """Resolve every unique slug to an embedded animated WebP data URI."""
    slugs: list[str] = []
    for day in ROUTINE["days"]:
        for ex in day["exercises"]:
            if ex["slug"] and ex["slug"] not in slugs:
                slugs.append(ex["slug"])

    media: dict[str, str] = {}
    for i, slug in enumerate(slugs, 1):
        print(f"[{i}/{len(slugs)}] {slug}")
        gif_url = gif_url_for_slug(slug)
        webp = build_webp(slug, gif_url)
        media[slug] = to_data_uri(webp)
        print(f"        gif={gif_url.rsplit('/', 1)[-1]}  webp={len(webp) // 1024} KB")
    return media


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0f172a">
<meta name="apple-mobile-web-app-capable" content="yes">
<title>__TITLE__</title>
<style>
  :root {
    --bg: #0f172a; --card: #1e293b; --card2: #334155; --ink: #f1f5f9;
    --muted: #94a3b8; --accent: #22d3ee; --accent2: #a78bfa; --ok: #34d399;
    --line: #334155;
  }
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  html, body { margin: 0; padding: 0; }
  body {
    background: var(--bg); color: var(--ink);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    padding-bottom: env(safe-area-inset-bottom);
  }
  header {
    padding: 18px 16px 12px; position: sticky; top: 0; z-index: 20;
    background: linear-gradient(180deg, #0f172a 70%, rgba(15,23,42,.85));
    backdrop-filter: blur(8px); border-bottom: 1px solid var(--line);
  }
  h1 { font-size: 20px; margin: 0; letter-spacing: .3px; }
  header p { margin: 4px 0 0; color: var(--muted); font-size: 13px; }
  nav { display: flex; gap: 8px; overflow-x: auto; padding: 10px 0 0; scrollbar-width: none; }
  nav::-webkit-scrollbar { display: none; }
  nav button {
    flex: 0 0 auto; border: 1px solid var(--line); background: var(--card);
    color: var(--muted); padding: 8px 14px; border-radius: 999px; font-size: 14px;
    font-weight: 600; cursor: pointer;
  }
  nav button.active { background: var(--accent); border-color: var(--accent); color: #04222a; }
  main { padding: 14px 12px 40px; max-width: 720px; margin: 0 auto; }
  .day-head { display: flex; align-items: baseline; gap: 10px; margin: 4px 4px 12px; }
  .day-head h2 { font-size: 17px; margin: 0; }
  .day-head span { color: var(--accent2); font-size: 13px; font-weight: 600; }
  .card {
    background: var(--card); border: 1px solid var(--line); border-radius: 16px;
    margin-bottom: 12px; overflow: hidden;
  }
  .card.done { opacity: .55; }
  .card .top { display: flex; gap: 12px; padding: 12px; }
  .media {
    position: relative; flex: 0 0 108px; width: 108px; height: 108px;
    border-radius: 12px; overflow: hidden; background: #0b1220;
  }
  .media img { width: 100%; height: 100%; object-fit: cover; display: block; }
  .media .reps {
    position: absolute; left: 6px; bottom: 6px; background: rgba(4,34,42,.85);
    color: var(--accent); font-size: 11px; font-weight: 700; padding: 2px 6px; border-radius: 6px;
  }
  .info { flex: 1 1 auto; min-width: 0; }
  .info h3 { font-size: 15px; margin: 0 0 6px; line-height: 1.25; }
  .scheme { color: var(--accent); font-size: 13px; font-weight: 700; margin-bottom: 6px; }
  .cue { color: var(--muted); font-size: 12.5px; line-height: 1.45; }
  .sets { display: flex; gap: 8px; padding: 0 12px 12px; }
  .sets button {
    flex: 1; padding: 9px 0; border-radius: 10px; border: 1px solid var(--line);
    background: var(--card2); color: var(--muted); font-weight: 700; font-size: 13px; cursor: pointer;
  }
  .sets button.on { background: var(--ok); border-color: var(--ok); color: #052e22; }
  .link { display: block; padding: 0 12px 12px; color: var(--muted); font-size: 11px; text-decoration: none; }
  .link:hover { color: var(--accent); }
  .notes { background: var(--card); border: 1px solid var(--line); border-radius: 16px; padding: 14px 16px; margin-top: 8px; }
  .notes h3 { margin: 0 0 10px; font-size: 15px; }
  .notes dl { margin: 0; }
  .notes dt { color: var(--accent2); font-weight: 700; font-size: 13px; margin-top: 10px; }
  .notes dd { margin: 2px 0 0; color: var(--muted); font-size: 12.5px; line-height: 1.45; }
  .foot { color: #64748b; font-size: 11px; text-align: center; padding: 20px 16px 0; line-height: 1.5; }
  .reset { display: block; margin: 14px auto 0; background: none; border: 1px solid var(--line);
           color: var(--muted); padding: 8px 16px; border-radius: 999px; font-size: 12px; cursor: pointer; }
</style>
</head>
<body>
<header>
  <h1>__TITLE__</h1>
  <p>__SUBTITLE__</p>
  <nav id="nav"></nav>
</header>
<main id="main"></main>
<script>
const ROUTINE = __DATA__;
const MEDIA = __MEDIA__;
const STORE = "rutina-franco-v1";
const state = JSON.parse(localStorage.getItem(STORE) || '{"day":0,"done":{}}');

function save() { localStorage.setItem(STORE, JSON.stringify(state)); }

function renderNav() {
  const nav = document.getElementById('nav');
  nav.innerHTML = '';
  ROUTINE.days.forEach((d, i) => {
    const b = document.createElement('button');
    b.textContent = d.label + ' · ' + d.focus;
    b.className = i === state.day ? 'active' : '';
    b.onclick = () => { state.day = i; save(); render(); };
    nav.appendChild(b);
  });
}

function render() {
  renderNav();
  const d = ROUTINE.days[state.day];
  const main = document.getElementById('main');
  main.innerHTML = '';
  const head = document.createElement('div');
  head.className = 'day-head';
  head.innerHTML = '<h2>' + d.label + '</h2><span>' + d.focus + '</span>';
  main.appendChild(head);

  d.exercises.forEach((ex, i) => {
    const key = d.id + ':' + i;
    const done = state.done[key] || [false, false, false];
    const card = document.createElement('div');
    card.className = 'card' + (done.every(Boolean) ? ' done' : '');

    const top = document.createElement('div');
    top.className = 'top';
    const img = MEDIA[ex.slug] || '';
    top.innerHTML =
      '<div class="media"><img loading="lazy" src="' + img + '" alt="' + ex.name + '">' +
      '<span class="reps">' + ex.scheme + '</span></div>' +
      '<div class="info"><h3>' + ex.name + '</h3>' +
      '<div class="scheme">' + ex.scheme + '</div>' +
      '<div class="cue">' + ex.cue + '</div></div>';
    card.appendChild(top);

    const sets = document.createElement('div');
    sets.className = 'sets';
    const total = parseInt((ex.scheme.match(/^(\\d+)/) || [0, 3])[1], 10) || 3;
    for (let s = 0; s < total; s++) {
      const b = document.createElement('button');
      b.textContent = 'Serie ' + (s + 1);
      b.className = done[s] ? 'on' : '';
      b.onclick = () => {
        state.done[key] = state.done[key] || [false, false, false];
        state.done[key][s] = !state.done[key][s];
        save(); render();
      };
      sets.appendChild(b);
    }
    card.appendChild(sets);

    const link = document.createElement('a');
    link.className = 'link';
    link.href = 'https://fitcron.com/exercise/' + ex.slug + '/';
    link.target = '_blank';
    link.rel = 'noopener';
    link.textContent = 'Ver ficha completa en FitCron ↗';
    card.appendChild(link);
    main.appendChild(card);
  });

  const notes = document.createElement('div');
  notes.className = 'notes';
  notes.innerHTML = '<h3>Pautas generales</h3><dl>' +
    ROUTINE.notes.map(n => '<dt>' + n[0] + '</dt><dd>' + n[1] + '</dd>').join('') +
    '</dl>';
  main.appendChild(notes);

  const foot = document.createElement('div');
  foot.className = 'foot';
  foot.innerHTML = ROUTINE.note_footer +
    '<br>Animaciones: fitcron.com — uso personal.' +
    '<button class="reset" id="reset">Borrar progreso</button>';
  main.appendChild(foot);
  document.getElementById('reset').onclick = () => {
    if (confirm('¿Borrar todas las series marcadas?')) {
      state.done = {}; save(); render();
    }
  };
}

render();
</script>
</body>
</html>
"""


def render_html(media: dict[str, str]) -> str:
    return (
        HTML_TEMPLATE
        .replace("__TITLE__", ROUTINE["title"])
        .replace("__SUBTITLE__", ROUTINE["subtitle"])
        .replace("__DATA__", json.dumps(ROUTINE, ensure_ascii=False))
        .replace("__MEDIA__", json.dumps(media))
    )


def main() -> None:
    if not ROUTINE["days"]:
        sys.exit("No routine defined.")
    media = build_media()
    html = render_html(media)
    OUTPUT.write_text(html, encoding="utf-8")
    (ROOT / "index.html").write_text(html, encoding="utf-8")
    size_mb = OUTPUT.stat().st_size / (1024 * 1024)
    print(f"\nEscrito {OUTPUT.name} + index.html ({size_mb:.2f} MB) con {len(media)} GIFs embebidos.")


if __name__ == "__main__":
    main()
