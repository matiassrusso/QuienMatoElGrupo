# Estado del proyecto — notas de trabajo

> Este archivo es para retomar el proyecto sin perder contexto. Lo voy actualizando a medida que avanzo. No es documentación de usuario (para eso está el README).

Última actualización: 2026-07-07 (sesión 3, cierre)

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

### Tarea #2 — reskin del resto de la app (en curso, no terminada)

`App.css` (1300+ líneas) resultó estar armado con un montón de colores hardcodeados uno-por-uno (variantes de navy, cyan `#7cd6ff`, naranja `#f6a05d`, coral `#ff7a59`) en vez de un sistema de tokens — confirma la queja original de "flowcodeado". En vez de tocar cada regla a mano, hice:

1. Reescribí los tokens de `:root` a la paleta del expediente (bg `#151312`, texto `#f1ede4`, acento único rojo `#9a2c2c`, radios de 2-6px en vez de 14-36px)
2. Escribí un script Python (`reskin_css*.py`, quedaron en el tmp del job, no en el repo) que recorre el resto de `App.css` y remapea cualquier color no-neutro al mismo tono rojo vía HSV (rota el hue a 0°, conserva luminosidad, achica saturación de los que eran muy vívidos). Dos iteraciones fallidas antes de que funcionara bien:
   - v1 usaba saturación HLS para detectar "es gris/neutro" → confundía blancos casi-puros (`#f7fbff`) con colores vívidos y los pintaba de rojo
   - v2 con saturación HSV pero threshold de "spread" crudo → perdía navys oscuros reales (`rgba(6,16,30,..)`) por tener spread bajo en términos absolutos
   - v3 (la que quedó) usa saturación HSV pura, sin threshold de spread — anduvo bien
3. Reemplacé `font-family: "Syne"` por `Georgia, "Times New Roman", serif` en los 4 headers (h1/h2/h3/podium-medal), consistente con el serif de `CaseHero`
4. Saqué el glassmorphism (`backdrop-filter: blur`), los blobs de glow decorativos (`.app::before/::after`) y el sheen diagonal (`::before` con gradiente) — no calzan con el look plano/mate del expediente
5. Verificado con build+lint+test (verdes) y visualmente en navegador inyectando un resultado mock temporal en `App.tsx` (revertido antes de terminar) — veredicto, insights, dinámica de grupo, playback y share-card se ven coherentes con la paleta nueva

**Sesión 3 (2026-07-07) — cierre de la tarea:**
- `ActivityHeatmap.tsx:44-45` — reemplazado el naranja viejo (`rgba(246, 160, 93, ...)`) por `rgba(153, 72, 72, ...)`, el mismo rojo que ya usa la leyenda del heatmap en `App.css` (`.heatmap-legend-cell-*`). Ahora la escala de intensidad es consistente de punta a punta.
- `ShareCard.tsx` — reescrito el SVG completo del share-card (fondo, paneles, textos, bordes) con la paleta del expediente (`#151312`/`#1c1815`/`#201b17` de fondo, acento `#9a2c2c`/`#c23a3a`, texto `#f1ede4`/`#a29c92`) y tipografías Georgia/Space Mono. Se eliminó el `<linearGradient>` decorativo del panel izquierdo (quedó fill plano `#201b17`), consistente con la decisión de sacar glassmorphism/sheen del resto de la app.
- `ActivityChart.tsx` — ejes, tooltip y barras de Recharts migrados a los tokens: barras activas en `#9a2c2c`, barras en cero mensajes en un rojo apagado `#5c3535` (antes navy/amber sin relación con la paleta), tooltip con fondo/borde/radio acordes (`#1c1815`, `rgba(216,210,200,0.14)`, `4px`).
- Verificación visual completa con datos reales: se generó un export sintético de WhatsApp (5 miembros, ~170 mensajes, patrón de desgaste con reactivación) y se corrió contra el backend local (`/analizar`) para obtener el JSON real de análisis. Se inyectó temporalmente en `App.tsx` (mismo hack de la sesión anterior, revertido con `git checkout` al terminar) para revisar en el navegador: hero, veredicto, stats, podio (`Podium`), dinámica de grupo, playback, timeline, comparación de miembros (`MemberCompare`), autopsia (`AutopsyPanel`), heatmap, chart, tabla completa (`MembersTable`) y placa de share. Todo coherente con la paleta roja/dossier.
- `git checkout -- frontend/src/App.tsx` dejó ese archivo sin diff (el hack de QA nunca queda commiteado).
- Build, lint y test (10/10) verdes después de los cambios.

**Pendiente, no bloqueante:**
- Los kickers (`.eyebrow`, `.section-kicker`, etc.) quedaron con Manrope; la idea original era pasarlos a Space Mono para eco con `CaseHero`. Cosmético, se puede hacer en cualquier momento.
- `.heatmap-day` en `App.css` (color `#dce7f8`) quedó fuera del remap automático por estar justo debajo del umbral de saturación del script — es un azulado muy tenue, casi imperceptible, pero no es un token real.

Con esto, la Tarea #2 (reskin del resto de la app) quedó terminada y **commiteada y pusheada** (commit `d88a5ba`, CI verde en GitHub).

### Tarea #4 — veredicto redactado por IA (BYOK)

Decisión de modelo de negocio (Tarea #3, cerrada): **cada persona que usa la web conecta su propia cuenta/token de IA** (BYOK - bring your own key). No hay key compartida del lado del servidor, no hay cuentas, no hay billing nuestro. Encaja con el pitch de privacidad existente ("todo se procesa en memoria, nada se persiste") — el backend sigue siendo 100% stateless, la key nunca se guarda en el servidor, solo se reenvía en el momento del pedido.

Dato clave que simplificó todo: `Message.text` (contenido real de los mensajes) se parsea en `backend/parser.py` pero nunca sale hacia `AnalysisResult`/`AnalysisResultOut` — el análisis solo usa `author` + `timestamp`. Por eso el veredicto de IA no necesita mandar texto real del chat a ningún proveedor externo: alcanza con los mismos datos agregados que ya se calculan (stats por miembro, patrón, fases, causa por reglas como pista/referencia). Cero contenido real del chat viaja a un tercero.

**Implementado:**
- `backend/llm.py` (nuevo) — `call_llm(provider, api_key, model, system_prompt, user_prompt)`, dispatch simple a Anthropic (`/v1/messages`) o OpenAI (`/v1/chat/completions`) vía `httpx`. Mapea 401 → "la key no es válida", otros errores (429, 5xx, etc.) incluyen el `error.message` real del proveedor vía `_extract_error_message()`. Nunca loguea la key ni el payload.
- `backend/schemas.py` — `VeredictoIARequest`/`VeredictoIAResponse`.
- `backend/main.py` — nuevo endpoint `POST /veredicto-ia`, arma el prompt a partir de los datos agregados (`build_verdict_prompt`) y devuelve el texto generado. Errores del proveedor → HTTP 502.
- `backend/requirements.txt` — agregado `httpx==0.28.1`.
- Tests nuevos en `backend/tests/test_api.py` (`VeredictoIAApiTests`): mockean `call_llm`, sin llamadas reales a la red.
- `frontend/src/aiSettings.ts` (nuevo) — `loadAISettings`/`saveAISettings` sobre `localStorage` (key `qmeg_ai_settings`), reusable a futuro por el clon del grupo.
- `frontend/src/api.ts` — `generarVeredictoIA(settings, result, tone)`.
- `frontend/src/components/AIVerdict.tsx` (nuevo) — formulario (proveedor/key/modelo opcional) con disclaimer de privacidad visible, botón "Generar veredicto con IA" una vez configurado, estados de loading/error. Montado en `App.tsx` justo después de `VerdictPanel`.
- CSS nuevo en `App.css` (`.ai-verdict*`) reusando los tokens existentes (`--panel`, `--accent`, `--radius-*`), sin inventar paleta nueva.

**Verificado end-to-end en el navegador (dos rondas):**
1. Con una key falsa: frontend guarda en localStorage → llama al backend local → backend llama a la API real de Anthropic → recibe 401 → lo traduce a "La API key de Anthropic no es válida." → se muestra en la UI. Confirmado que la key persiste entre reloads (no vuelve a pedir el formulario).
2. Con una key real del usuario (OpenAI): el pedido llegó a devolver **429** ("OpenAI devolvio un error (429)."). El mensaje original no incluía el detalle del proveedor (cuota agotada vs. rate limit vs. otra cosa), así que se mejoró `backend/llm.py` con `_extract_error_message()` — extrae `error.message` del cuerpo JSON de la respuesta (formato común a Anthropic y OpenAI) y lo agrega al mensaje de error. Cubierto con test nuevo `backend/tests/test_llm.py` (3 casos: extrae mensaje anidado, devuelve `None` si el body no es JSON, devuelve `None` si falta la key `error`). **No se volvió a probar en el navegador tras este fix** (se cortó la sesión antes) — la próxima vez que se pruebe con una key real, el mensaje de 429/error debería traer el detalle real del proveedor.

El camino feliz (respuesta exitosa del LLM, texto generado visible) todavía no se vio en pantalla — la key de OpenAI probada devolvió 429 antes de llegar a generar texto. Si se prueba de nuevo y el 429 persiste, es un tema de cuota/billing de esa cuenta de OpenAI, no del código.

Build, lint y test (10/10 frontend, 13/13 backend) verdes. Falta commitear.

### Skills que estoy usando

- `emil-design-eng` — polish de UI, decisiones de motion/animación
- `dataviz` — rediseño de `ActivityHeatmap` / `ActivityChart`
- `prototype` — mockups descartables para validar dirección antes de tocar el código real
- `web-design-guidelines` — pasada de accesibilidad al final

No hizo falta instalar ninguna skill nueva.

### TODO rediseño + IA

- [x] Prototipo descartable del hero/concepto narrativo — usuario eligió variante C, ya foldeada en `CaseHero.tsx`
- [x] Reskin del resto de la app — tokens/paleta/tipografía en `App.css` + `ActivityHeatmap.tsx`, `ShareCard.tsx`, `ActivityChart.tsx` migrados, verificado visualmente con datos reales. **Commiteado y pusheado** (`d88a5ba`).
- [x] Elegir modelo de integración de IA — decidido BYOK (cada usuario conecta su propia key de Anthropic u OpenAI, sin cuenta/billing nuestro)
- [x] IA integración 1: veredicto/causa probable redactado por LLM — endpoint `/veredicto-ia` + `AIVerdict.tsx`, verificado end-to-end (ver detalle arriba). Falta commitear.
- [ ] IA integración 2: "clon" del grupo — chat efímero in-page en la misma sesión, con el contexto ya parseado en memoria, sin persistencia (mantiene el modelo de privacidad actual). **Pendiente una decisión de arquitectura propia** (ver abajo) antes de empezar a codear.
- [ ] IA integración 3 (v2, después): bot de Telegram con el mismo clon. Requiere proceso corriendo 24/7 y persistir contexto — rompe el pitch actual de "todo en memoria", hay que decidir un modelo de privacidad nuevo cuando se aborde

## Ideas sueltas / por definir

- **Decisión pendiente para el clon del grupo (Tarea #5):** a diferencia del veredicto, el clon necesita texto real de mensajes para sonar como el grupo (tono, chistes internos), no solo agregados. Como el backend no persiste nada entre requests, hay que elegir entre (a) re-subir el .zip en cada mensaje del chat (mantiene el "cero estado en el servidor" al 100%, pero re-parsear en cada mensaje es más pesado para el usuario) o (b) una sesión efímera en memoria con TTL (más fluido, pero introduce estado server-side por primera vez, aunque sea solo RAM). No decidido todavía.
- No decidido: paleta final de acento (¿rojo/sangre por la temática, o algo menos literal como el lima de Hildén & Kaira?)
- No decidido: si el "clon" imita el tono general del grupo o permite elegir "hablar como [miembro específico]"
