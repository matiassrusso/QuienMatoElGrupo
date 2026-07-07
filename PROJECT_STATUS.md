# Estado del proyecto — notas de trabajo

> Este archivo es para retomar el proyecto sin perder contexto. Lo voy actualizando a medida que avanzo. No es documentación de usuario (para eso está el README).

Última actualización: 2026-07-07

## Qué es esto

App que analiza exports de WhatsApp y calcula, con métricas, cómo se fue apagando un grupo. Backend FastAPI + frontend React/Vite.

- Frontend: https://quien-mato-el-grupo.vercel.app/
- Backend: https://quienmatoelgrupo-production.up.railway.app

## Hecho hasta ahora (fundacional)

- [x] Core funcional completo: parser de exports (Android/iOS), análisis (heatmap, timeline, clasificador de patrón, causa probable por reglas), UI con ~20 componentes
- [x] Fix: subir un archivo no-zip devolvía 500, ahora devuelve 400 (`backend/parser.py`)
- [x] Tests de frontend arrancados (vitest, 10 tests sobre `utils/format.ts`)
- [x] CI en GitHub Actions (`.github/workflows/ci.yml`): backend unittest + frontend lint/test/build
- [x] Deploy: backend en Railway, frontend en Vercel, conectados vía `VITE_API_URL`
- [x] `skills-lock.json` y `.agents/` (cruft de una herramienta de skills sin usar) eliminados

## Deuda pendiente (de la auditoría inicial, no bloqueante)

- [ ] Tests de componentes React (ninguno cubierto todavía, solo `format.ts`)
- [ ] Tests de la lógica del clasificador en `backend/analysis.py` (conversation_pattern / probable_cause) — solo se ejercen indirectamente
- [ ] Limpiar assets sin usar: `frontend/src/assets/react.svg`, `vite.svg`, `hero.png`

## Fase actual: rediseño + IA

El usuario quiere convertir esto en una pieza de portfolio: "web pro, innovadora, atractiva, que parezca hecha por profesionales". Queja concreta sobre el diseño actual: demasiadas tarjetas, se siente "flowcodeado" (genérico, plantillero).

### Dirección de diseño acordada

Los nombres de componentes ya sugieren un concepto de "expediente forense" (`CaseIntro`, `AutopsyPanel`, `DeathTimeline`, `RevealSection`) que hoy no se explota — quedó como dashboard de cards en vez de narrativa.

Referencias revisadas (galerías: Awwwards, Siteinspire, Land-book, CSS Design Awards, Mindsparkle, Httpster, 21st.dev):

- **[MONOLOG](https://bymonolog.com/)** — tipografía display gigante como hero, fondo oscuro con grano/textura y luces difuminadas, texto que se revela palabra por palabra con el scroll.
- **[Hildén & Kaira](https://www.hildenkaira.fi/)** — titular editorial serif con efecto cromado/líquido, bloques de color planos (crema/lima), frases contundentes tipo statement.

Plan de dirección:
- Tipografía como protagonista (el veredicto como titular editorial gigante, no una card más)
- Scroll narrativo por secciones a pantalla completa, no grid apretado
- Paleta oscura acotada con grano sutil + un solo color de acento
- Los datos (heatmap, stats) como piezas editoriales grandes, no widgets chicos

### Veredicto del prototipo

**Ganó la variante C ("Expediente"), tal cual, sin mezclar elementos de A o B.** Foldeada al código real:

- `frontend/src/components/CaseHero.tsx` — nuevo componente de landing (pestañas laterales, sello "En investigación", tipografía Space Mono/Georgia, teaser con scroll-reveal)
- `frontend/src/components/WordReveal.tsx` — promovido de prototype a componente real reusable
- Estilos `.case-hero-*` movidos a `App.css` (fuente Space Mono agregada al `@import` existente, mismo patrón que Manrope/Syne)
- `CaseIntro.tsx` (grid de 3 cards) eliminado — su contenido pasó a prosa en el teaser de `CaseHero`
- Carpeta `frontend/src/prototype/` eliminada completa (variantes A/B + switcher, ya cumplieron su función)
- Verificado: build, lint y tests (10/10) pasan; revisado visualmente en navegador

Esto solo cubre la pantalla previa al análisis. El header/resultados post-análisis sigue con el diseño viejo — es la Tarea #2.

### Skills que estoy usando

- `emil-design-eng` — polish de UI, decisiones de motion/animación
- `dataviz` — rediseño de `ActivityHeatmap` / `ActivityChart`
- `prototype` — mockups descartables para validar dirección antes de tocar el código real
- `web-design-guidelines` — pasada de accesibilidad al final

No hizo falta instalar ninguna skill nueva.

### TODO rediseño + IA

- [x] Prototipo descartable del hero/concepto narrativo — usuario eligió variante C, ya foldeada en `CaseHero.tsx`
- [ ] Plan componente por componente para el resto de la app (header post-análisis, Podium, MembersTable, ActivityHeatmap, etc.) en la estética de expediente
- [ ] Elegir proveedor de LLM / conseguir API key (bloqueante para las dos features de IA de abajo)
- [ ] IA integración 1: veredicto/causa probable redactado por LLM (hoy es texto por reglas en `backend/analysis.py`, función que genera `probable_cause`)
- [ ] IA integración 2: "clon" del grupo — chat efímero in-page en la misma sesión, con el contexto ya parseado en memoria, sin persistencia (mantiene el modelo de privacidad actual)
- [ ] IA integración 3 (v2, después): bot de Telegram con el mismo clon. Requiere proceso corriendo 24/7 y persistir contexto — rompe el pitch actual de "todo en memoria", hay que decidir un modelo de privacidad nuevo cuando se aborde

## Ideas sueltas / por definir

- No decidido: proveedor de IA (Anthropic/OpenAI/otro) ni manejo de API key en producción
- No decidido: paleta final de acento (¿rojo/sangre por la temática, o algo menos literal como el lima de Hildén & Kaira?)
- No decidido: si el "clon" imita el tono general del grupo o permite elegir "hablar como [miembro específico]"
