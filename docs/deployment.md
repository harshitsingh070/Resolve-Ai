# Deployment — ResolveAI (Vercel + Render, SQLite)

**Locked architecture, no Postgres/Redis/Docker.** This doc is reviewer-accessible: local run is primary, hosted is optional.

## Option A — Local (recommended for reviewer, SQLite permanent)

```powershell
# backend (http://localhost:8000)
cd backend
python -m venv venv; .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env   # set GROQ_API_KEY
python seed.py
uvicorn app.main:app --reload --port 8000
# -> http://localhost:8000/docs

# frontend (http://localhost:5173)
cd frontend
npm install
npm run dev
# VITE_API_URL defaults to http://localhost:8000
```

## Option B — Hosted (free tier, ephemeral FS caveat)

### Frontend → Vercel
1. Import `frontend/` as Vercel project (framework: Vite)
2. Build: `npm run build`, Output: `dist`
3. Env: `VITE_API_URL=https://<your-backend>.onrender.com`
4. Deploy — `vercel.json` already handles SPA rewrites.

### Backend → Render (or Fly/Railway)
1. New Web Service → repo `harshitsingh070/Resolve-Ai`, Root: `backend`
2. Build: `pip install -r requirements.txt`
3. Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT` (`render.yaml` + `Procfile` already)
4. Env: `GROQ_API_KEY` (secret), `GROQ_MODEL=openai/gpt-oss-20b`, `DATABASE_URL=sqlite:///./resolveai.db`
5. Health: `GET /api/health` → `{"status":"ok"}`

### SQLite persistence note (important)
* Render free tier has **ephemeral filesystem** — `resolveai.db` may reset on deploy/sleep (up to few hours). For **demo** this is acceptable: `seed.py` recreates 3 customers/4 bookings, and `GET /api/session` + `POST /api/chat` work immediately.
* For **reviewer** we recommend **local** run (permanent file) — no infra.
* If hosted persistence proves unreliable, smallest alternative is **Turso** (SQLite) or **Neon** (Postgres) — change only `DATABASE_URL`, no code redesign. Not added by default to keep 6-hour scope.

## Production checklist
- [ ] `GROQ_API_KEY` set server-only (never in frontend)
- [ ] `VITE_API_URL` points to backend
- [ ] `python seed.py` run once after first deploy
- [ ] `GET /api/health` 200
- [ ] `POST /api/chat` for `SK4821X/TR1190B/WL7742` → actions + escalations as per demo script

## Architecture unchanged
No Docker/K8s, single `uvicorn` + `Vite` static, SQLite file.
