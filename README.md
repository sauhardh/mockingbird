# Birdss — Setup & Run

This document describes what to put in the backend and frontend `.env` files and how to install and run the backend, the isolated RAG service, and the frontend (Vite).

**Env Files**
- **Backend (.env)**: create a file at `birdss_backend/.env` with the following entries:

```
UCN_API="your api key"
GROQ_API_KEY=:your api key"
```

- **Frontend (.env)**: create a file at `Birdss/.env` (Vite reads `VITE_` prefixed variables) with the following entries:

```
VITE_AI_STUDIO_KEY="your key"
VITE_BIRD_API_URL="http://127.0.0.1:8000"
VITE_RAG_API_URL="http://127.0.0.1:8005"
VITE_OPENWEATHER_KEY="your key"
VITE_GROQ_API_KEY="your key"
VITE_GROQ_MODEL="llama-3.1-8b-instant"
# Free MAP_KEY at https://firms.modaps.eosdis.nasa.gov/api/map_key/ — leave blank to fall back to AI fire risk
VITE_NASA_FIRMS_KEY=""
```

**Install & Run: Backend (FastAPI)**
uv sync 

```powershell
uv run uvicorn app:app 
```

**Install & Run: RAG service (isolated)

- The isolated RAG service lives in `birdss_backend/dataset/rag` and has its own `pyproject.toml`.

```powershell
cd birdss_backend\dataset\rag
uv sync
uv run app.py

Notes:
- The RAG service depends on FAISS and sentence-transformers; installation may take a while and require a compatible Python and wheel availability on Windows. Consider using a Linux environment if you run into wheel build issues.

**Install & Run: Frontend (Vite + React)**

- From the project root or the `Birdss` folder:

```bash
cd Birdss
npm install
# create the .env file described above inside Birdss/
npm run dev
```

