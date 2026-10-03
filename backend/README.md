# JobMatch AI: Backend (Flask + MySQL)

REST API with TF-IDF + cosine-similarity recommendations, resume upload (PDF/TXT), saved jobs, applications and admin endpoints.

## Run locally
```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows  (macOS/Linux: source venv/bin/activate)
pip install -r requirements.txt
cp .env.example .env           # then edit .env (Windows: copy .env.example .env)
python app.py                  # creates tables, seeds skills/jobs and an admin user
```
Open http://127.0.0.1:5000. For quick local testing without MySQL, set `DATABASE_URL=sqlite:///local.db` in `.env`.

## Tests
```bash
pytest
```

## Endpoints
| Method | Route | Notes |
|---|---|---|
| POST | /auth/register, /auth/login, /auth/logout | session cookie, hashed passwords |
| GET/PUT | /profile | needs login |
| GET | /jobs?q=&location=&job_type=&page= | search + pagination |
| POST | /jobs/<id>/save, /jobs/<id>/apply | needs login, duplicates blocked |
| GET | /applications, /recommendations | needs login |
| GET | /skills/suggest?q= | up to 20 suggestions |
| POST | /match | live matching, `within_hours` = 24 or 72 |
| POST | /resume/upload | PDF/TXT, 2 MB max, processed in memory |
| POST/PATCH/GET | /admin/jobs, /admin/applications/<id>, /admin/stats | admin role only |

## Security notes
Passwords are hashed (Werkzeug), uploads are type/size checked and never stored, secrets come from `.env`. Set `ADMIN_PASSWORD` in `.env` before first run. Add CSRF protection and rate limiting before a public launch.
