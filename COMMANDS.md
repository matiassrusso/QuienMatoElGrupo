# Commands & Skills

Quick reference for all available skills and commands in this project.

## Skills (in XX Skills/)

Skills de Claude Code que se vienen usando activamente en este proyecto (según `PROJECT_STATUS.md`):

- `emil-design-eng` — polish de UI, decisiones de motion/animación
- `dataviz` — rediseño de `ActivityHeatmap` / `ActivityChart`
- `prototype` — mockups descartables para validar dirección antes de tocar código real
- `web-design-guidelines` — pasada de accesibilidad
- `impeccable` — `/impeccable init` para `PRODUCT.md`/`DESIGN.md`, `/impeccable shape` para briefs de diseño (ej. heatmap 3D)
- `webapp-testing` — Playwright headless para verificar prototipos e integraciones (WebGL vía software rendering en headless Chromium)

## Commands

### Correr local

```powershell
# Backend — OJO: no uses --reload en esta máquina (git-bash cuelga el subproceso de reload sin avisar)
cd backend
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m uvicorn main:app --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

Notas privadas (`PRODUCT.md`, `DESIGN.md`, `.impeccable/`, `PROJECT_STATUS.md`) viven en un historial git separado (`.git-private`), commiteado aparte del historial público.
