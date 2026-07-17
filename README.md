![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-61DAFB?style=flat&logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat&logo=typescript&logoColor=white)
![Privacy](https://img.shields.io/badge/data-in--memory%20only-brightgreen?style=flat)
# ¿Quién Mató el Grupo?

Analytics de actividad para grupos de WhatsApp — descubrí quién dejó de participar y cuándo, a partir de tu export de chat.

Activity analytics for WhatsApp groups — find out who went quiet and when, from your own chat export.

---

## Demo en producción / Live demo

- **App:** https://quien-mato-el-grupo.vercel.app/
- **API:** https://quien-mato-el-grupo-api.onrender.com

## Cómo funciona / How it works

Subís el archivo `.zip` que exportás desde WhatsApp (Chat → Exportar chat) y la app procesa todo **en memoria**, sin guardar ni persistir ningún dato en ningún momento.

Upload the `.zip` file exported from WhatsApp (Chat → Export chat) and the app processes everything **in memory**, with no data ever saved or persisted.

## Stack

- **Backend:** Python, FastAPI
- **Frontend:** React, TypeScript
- **Visualización / Visualization:** Recharts

## Funcionalidades / Features

- Ranking de inactividad con podio y tabla completa
- Gráfico de actividad a lo largo del tiempo
- Procesamiento 100% en memoria — privacidad garantizada, no se guarda ningún mensaje

- Inactivity ranking with podium and full table
- Activity chart over time
- 100% in-memory processing — privacy by design, no message is ever stored

## Correr el proyecto localmente / Running locally

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

> Nota: verificá los comandos exactos contra los archivos de configuración reales del repo.
> Note: check exact commands against the repo's actual config files.

## Privacidad / Privacy

Ningún mensaje ni metadato del chat se almacena en disco o base de datos — todo el análisis ocurre en memoria durante la sesión y se descarta al finalizar.

No message or chat metadata is stored to disk or database — all analysis happens in memory during the session and is discarded afterward.

### Sobre el clon conversacional (opcional) / About the conversational clone (optional)

La función de "clon del grupo" es la única excepción a lo anterior: para que el clon suene como el grupo (tono, chistes internos, muletillas), necesita texto real de los mensajes, no solo metadatos agregados. Al usarla, tu chat se guarda temporalmente en la memoria RAM del backend (nunca en disco) por un tiempo limitado y se borra automáticamente al expirar. El resto de la app (análisis, veredicto, heatmap, grafo de interacción) sigue siendo 100% in-memory-y-descartado-al-instante, sin excepción.

The "group clone" feature is the one exception to the above: to sound like the group (tone, inside jokes, verbal tics), it needs real message text, not just aggregated metadata. When you use it, your chat is temporarily kept in the backend's RAM (never on disk) for a limited time and is automatically discarded on expiry. The rest of the app (analysis, verdict, heatmap, interaction graph) remains 100% in-memory-and-discarded-instantly, no exception.

## Licencia / License

MIT
