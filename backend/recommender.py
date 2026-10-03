"""Hybrid recommender: TF-IDF + cosine similarity + structured matching."""
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

WEIGHTS = {"skill": 0.5, "exp": 0.2, "loc": 0.1, "title": 0.1, "pref": 0.1}  # configurable


def clean(text):
    return re.sub(r"[^a-z0-9+#. ]", " ", (text or "").lower())


def recommend(user, jobs, weights=WEIGHTS):
    """user: {skills:[], text, exp, locations:[], roles:[], job_type}
    jobs: [{id,title,description,skills:[],location,job_type,exp_min}]
    Returns jobs ranked with 'Profile Match' (compatibility, NOT hiring probability)."""
    if not jobs:
        return []
    user_skills = {s.strip().lower() for s in user.get("skills", []) if s.strip()}
    docs = [clean(f'{j["title"]} {j["description"]} ' + " ".join(j["skills"]) * 2) for j in jobs]
    query = clean(user.get("text", "") + " " + " ".join(user_skills) * 2)
    roles = clean(" ".join(user.get("roles", [])))
    titles = [clean(j["title"]) for j in jobs]

    vec = TfidfVectorizer(token_pattern=r"[a-z0-9+#.]+")
    m = vec.fit_transform(docs + [query, roles])          # ML step 1: TF-IDF vectors
    text_sim = cosine_similarity(m[len(docs)], m[:len(docs)])[0]   # ML step 2: cosine
    tv = TfidfVectorizer(token_pattern=r"[a-z0-9+#.]+").fit(titles + [roles])
    title_sim = cosine_similarity(tv.transform([roles]), tv.transform(titles))[0] if roles.strip() else [0] * len(jobs)

    out = []
    for i, j in enumerate(jobs):
        req = {s.lower() for s in j["skills"]}
        matched, missing = sorted(req & user_skills), sorted(req - user_skills)
        overlap = len(matched) / len(req) if req else 0
        skill = 0.6 * float(text_sim[i]) + 0.4 * overlap
        gap = max(0, j.get("exp_min", 0) - user.get("exp", 0))
        exp = max(0.0, 1 - gap / 3)
        locs = {l.strip().lower() for l in user.get("locations", [])}
        loc = 1.0 if not locs or j["location"].lower() in locs or j["location"].lower() == "remote" else 0.0
        pref = 1.0 if user.get("job_type") in (None, "", j["job_type"]) else 0.0
        score = (weights["skill"] * skill + weights["exp"] * exp + weights["loc"] * loc
                 + weights["title"] * float(title_sim[i]) + weights["pref"] * pref)
        if not matched and float(text_sim[i]) < 0.05:   # no skill overlap and no text similarity: irrelevant job
            score *= 0.25
        why = [f"{s} matches your profile" for s in matched]
        if loc: why.append(f'{j["location"]} matches your preference')
        if exp == 1: why.append("Experience level matches")
        out.append({**j, "match": round(score * 100), "why": why, "matched": matched, "missing": missing})
    return sorted(out, key=lambda r: r["match"], reverse=True)
