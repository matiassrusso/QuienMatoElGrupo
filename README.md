# Quien Mato el Grupo

Aplicacion para analizar exports de WhatsApp y detectar, con metricas, como se fue apagando la actividad de un grupo.

## Stack

- `backend/`: FastAPI, parseo de `.zip` exportados por WhatsApp y calculo de metricas.
- `frontend/`: React + TypeScript + Vite para subir el export y visualizar el informe.

## Requisitos

- Python 3.12
- Node.js 20+

## Backend

```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

## Frontend

```powershell
cd frontend
Copy-Item .env.example .env.local
npm install
npm run dev
```

Si PowerShell bloquea `npm.ps1`, usa `npm.cmd run dev`.

## Variables de entorno

El frontend lee `VITE_API_URL` desde `frontend/.env.local`.

```env
VITE_API_URL=http://localhost:8000
```

## Tests y verificaciones

### Backend

```powershell
cd backend
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

### Frontend

```powershell
cd frontend
npm run lint
npm run build
```

## Flujo de uso

1. Exporta un chat de WhatsApp con la opcion de incluir el archivo `.txt`.
2. Comprime el export en un `.zip` si WhatsApp no lo entrega ya empaquetado.
3. Sube el archivo desde la interfaz.
4. Elige la ventana temporal a analizar.
5. Revisa veredicto, timeline, heatmap y comparaciones.

## Notas

- El backend procesa el archivo en memoria; no persiste el contenido del chat.
- La URL del backend ya no esta hardcodeada en el frontend: puede cambiarse con `VITE_API_URL`.
- La suite de tests cubre parseo y el endpoint principal `/analizar`.
