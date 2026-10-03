# JobMatch AI: Smart Job Recommendation & Career Platform

Upload a PDF resume, see which job roles match your skills, which skills you are missing, and a step-by-step learning roadmap.

**Live demo:** _add your Netlify link here_

## Features
- Resume upload (PDF/TXT) with automatic skill, experience and location detection
- Role recommendations with a match % and a "Why this role?" explanation
- Skill-gap analysis, prioritised "what to learn" list and a 12-week career roadmap
- Job search with links to live LinkedIn, Indeed and Naukri searches (last ~3 days) and official company careers pages
- Login/Register with validation, profile, saved jobs, application tracker
- Responsive UI, light/dark mode, scroll animations, keyboard-accessible, Back button, footer

## Tech stack
| Layer | Technology |
|---|---|
| Frontend | HTML5, CSS3, vanilla JavaScript (ES6), PDF.js |
| Backend | Python, Flask, SQLAlchemy |
| Database | MySQL (SQLite works for local testing) |
| Recommendation | scikit-learn: TF-IDF + cosine similarity, plus weighted structured matching |
| Hosting (frontend) | Netlify |

## Project structure
```
jobmatch-ai/
├── frontend/   static site (index.html), deploys to Netlify as-is
└── backend/    Flask API, recommender, tests
```

## How the recommendation works
Profile/resume skills and text -> TF-IDF vectors -> cosine similarity with each job's text -> combined with experience, location, role and job-type matching -> weighted score (configurable in `backend/recommender.py`). The score is a **compatibility score, not a hiring probability**.

## Run the frontend
Open `frontend/index.html` in a browser (or use any static server). The frontend demo keeps data in memory and uses example role profiles; login/register do not create real accounts.

## Run the backend
See [backend/README.md](backend/README.md).

## Deploy the frontend to Netlify
Drag the `frontend` folder to https://app.netlify.com/drop, or import this repo in Netlify with publish directory `frontend` and no build command.

## Known limitations
- The Netlify frontend is a standalone demo and is not connected to the Flask backend yet.
- Job data is example role profiles; live openings come from the linked job boards.
- Skill detection uses a dictionary of ~40 common skills; scanned/image PDFs are not supported.

## Roadmap
Connect frontend to the API, JWT auth, admin dashboard UI, live job-feed integration, skill-synonym handling, embeddings-based matching.

## Author
Developed by **Tirupatnala** with love.

## License
MIT
