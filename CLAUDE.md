@AGENTS.md

# ¿Quién Mató el Grupo?

Analiza exports de WhatsApp y calcula, con métricas, cómo se fue apagando un grupo: quién dejó de participar, cuándo y con qué patrón. El proyecto más maduro y con más trabajo activo del portfolio ahora mismo — se está convirtiendo en la pieza insignia.

## Claude's Role

Acompañar el rediseño activo hacia la identidad "Expediente forense" (editorial/cinematográfico) y las features de IA (veredicto BYOK, "clon" conversacional del grupo). Éxito = que quien lo abra (usuario real o evaluador de portfolio) se vaya convencido de que el análisis es genuinamente agudo Y de que la narrativa es memorable.

If a session is drifting sin acercarse a eso, nudge me back: "¿Esto suma credibilidad de data science o sensación editorial/cinematográfica? Si no suma ninguna de las dos, ¿por qué lo estamos haciendo ahora?"

## Process

1. Sesión de trabajo se registra en `PROJECT_STATUS.md` (notas de retomar, qué se decidió, qué falta) — **leer ese archivo antes de arrancar cualquier sesión**
2. No asumir dirección de diseño/estética sin preguntar primero — el usuario ya lo pidió explícito varias veces
3. Implementación en `backend` (FastAPI) y/o `frontend` (React/TS)
4. Verificación visual con Playwright (`webapp-testing` skill) antes de dar por cerrado un cambio de UI
5. Tests en verde, build/lint verdes
6. Deploy: push a `main` (público) → Render + Vercel. Notas privadas (`PRODUCT.md`, `DESIGN.md`, `PROJECT_STATUS.md`, etc.) se commitean aparte en `.git-private`

## Key People

Solo yo (Matías).

## Folder Structure

- `backend/` — FastAPI: parser de exports (Android/iOS), análisis (heatmap, timeline, clasificador de patrón), grafo de interacción (`networkx`), changepoint detection (`ruptures`/PELT), LLM (veredicto BYOK + clon conversacional)
- `frontend/` — React/TS, ~20 componentes, identidad "Expediente forense"
- `00 System/` — scripts/config reusables de este proyecto (vacío por ahora)
- `01 Skills/` — skills en markdown de este proyecto (vacío por ahora)
- `02 Attachments/` — imágenes/screenshots (vacío por ahora)
- `03 Iteration Logs/` — notas de qué mejorar entre iteraciones (vacío por ahora; `PROJECT_STATUS.md` ya cumple ese rol a nivel sesión)

## Rules & Conventions

- **`(C)` prefix** — Archivos creados por Claude llevan prefijo `(C)`
- **Editing rule** — Antes de editar un archivo sin el prefijo `(C)`, pedir permiso primero
- **Skills** — Automatizaciones reusables de este proyecto van en `01 Skills/` como markdown, no como Claude Code skills
- **BYOK** — cada usuario conecta su propia key de IA (Anthropic/OpenAI/Gemini/Groq), sin key compartida del servidor; backend 100% stateless, el chat subido nunca se persiste
- **No asumir dirección de diseño** — preguntar primero, el usuario ya se quejó de estética genérica de IA antes
- Identidad visual: "Rojo Sello Oficial" `#9a2c2c`, "Negro Carpeta" `#151312`, Georgia + Space Mono, radios 2-6px, plano/mate (documentado en `DESIGN.md`/`PRODUCT.md`)

## Current Status

> **Last updated:** 2026-07-13
> **Status:** El más activo de los 5. En rediseño hacia "Expediente forense" — reskin general ya cerrado. Pendiente crítico sin arrancar: usuario no conforme con estética/interactividad del grafo de interacción (sesión activa al 2026-07-10).

Detalle sesión a sesión en `PROJECT_STATUS.md`. Pendiente: tests de componentes React, tests del clasificador, limpieza de assets sin usar.
