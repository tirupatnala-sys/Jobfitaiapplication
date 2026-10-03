import os, re, io, logging
from datetime import datetime, timedelta
from functools import wraps
from dotenv import load_dotenv
from flask import Flask, jsonify, request, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from recommender import recommend

load_dotenv()
app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ["SECRET_KEY"],
    SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL") or (
        f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
        f"@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', 3306)}/{os.getenv('DB_NAME')}?charset=utf8mb4"),
    MAX_CONTENT_LENGTH=3 * 1024 * 1024, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("FLASK_ENV") == "production",
)
logging.basicConfig(level=logging.INFO)
db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(10), default="user")
    skills = db.Column(db.Text, default="")          # comma-separated (compact version)
    experience_years = db.Column(db.Float, default=0)
    locations = db.Column(db.String(255), default="")
    roles = db.Column(db.String(255), default="")
    job_type = db.Column(db.String(30), default="")
    bio = db.Column(db.Text, default="")


class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False, index=True)
    company = db.Column(db.String(150))
    description = db.Column(db.Text)
    location = db.Column(db.String(100), index=True)
    job_type = db.Column(db.String(30))
    exp_min = db.Column(db.Float, default=0)
    salary = db.Column(db.String(40))
    skills = db.Column(db.Text)                       # comma-separated
    active = db.Column(db.Boolean, default=True, index=True)
    trusted = db.Column(db.Boolean, default=False, index=True)   # verified company
    posted = db.Column(db.DateTime, default=datetime.utcnow, index=True)  # UTC

    def to_dict(self):
        return dict(id=self.id, title=self.title, company=self.company, description=self.description or "",
                    location=self.location, job_type=self.job_type, exp_min=self.exp_min,
                    salary=self.salary, trusted=bool(self.trusted), posted=(self.posted.isoformat() + 'Z') if self.posted else None, skills=[s.strip() for s in (self.skills or "").split(",") if s.strip()])


class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.ForeignKey("user.id"), index=True)
    job_id = db.Column(db.ForeignKey("job.id"))
    status = db.Column(db.String(20), default="Applied")
    __table_args__ = (db.UniqueConstraint("user_id", "job_id"),)


class SavedJob(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.ForeignKey("user.id"), index=True)
    job_id = db.Column(db.ForeignKey("job.id"))
    __table_args__ = (db.UniqueConstraint("user_id", "job_id"),)


class Skill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False, index=True)


LANGS = ("Python,Java,JavaScript,TypeScript,C,C++,C#,Go,Rust,Kotlin,Swift,PHP,Ruby,Scala,R,MATLAB,Dart,Perl,Lua,Haskell,"
         "Elixir,Clojure,COBOL,SQL,HTML,CSS,Bash,PowerShell,Objective-C,Julia,Flask,Django,FastAPI,React,Angular,Vue,Node.js,"
         "Spring Boot,Docker,Kubernetes,AWS,Git,Linux,MySQL,PostgreSQL,MongoDB,Pandas,NumPy,Scikit-learn,TensorFlow,REST API,Excel").split(",")


def login_required(role=None):
    def deco(f):
        @wraps(f)
        def wrapper(*a, **kw):
            uid = session.get("user_id")
            if not uid:
                return jsonify(error="Login required"), 401
            if role and session.get("role") != role:
                return jsonify(error="Forbidden"), 403
            return f(*a, **kw)
        return wrapper
    return deco


def split(s): return [x.strip() for x in (s or "").split(",") if x.strip()]


@app.post("/auth/register")
def register():
    d = request.get_json() or {}
    if not all(d.get(k) for k in ("name", "email", "password")) or "@" not in d["email"]:
        return jsonify(error="Valid name, email and password required"), 400
    if len(d["password"]) < 8:
        return jsonify(error="Password must be at least 8 characters"), 400
    if User.query.filter_by(email=d["email"].lower()).first():
        return jsonify(error="Email already registered"), 409
    db.session.add(User(name=d["name"], email=d["email"].lower(), password_hash=generate_password_hash(d["password"])))
    db.session.commit()
    return jsonify(message="Registered"), 201


@app.post("/auth/login")
def login():
    d = request.get_json() or {}
    u = User.query.filter_by(email=(d.get("email") or "").lower()).first()
    if not u or not check_password_hash(u.password_hash, d.get("password", "")):
        app.logger.warning("Failed login for %s", d.get("email"))
        return jsonify(error="Invalid credentials"), 401
    session.clear(); session["user_id"], session["role"] = u.id, u.role
    return jsonify(message="Logged in", role=u.role)


@app.post("/auth/logout")
def logout():
    session.clear(); return jsonify(message="Logged out")


@app.route("/profile", methods=["GET", "PUT"])
@login_required()
def profile():
    u = db.session.get(User, session["user_id"])
    if request.method == "PUT":
        d = request.get_json() or {}
        for k in ("bio", "skills", "locations", "roles", "job_type"):
            if k in d: setattr(u, k, d[k])
        if "experience_years" in d: u.experience_years = float(d["experience_years"])
        db.session.commit()
    fields = [u.skills, u.locations, u.roles, u.job_type, u.bio, u.experience_years]
    return jsonify(name=u.name, email=u.email, skills=u.skills, locations=u.locations, roles=u.roles,
                   job_type=u.job_type, bio=u.bio, experience_years=u.experience_years,
                   completion=round(100 * sum(bool(f) for f in fields) / len(fields)))


@app.get("/jobs")
def jobs():
    q = Job.query.filter_by(active=True)
    if v := request.args.get("q"):
        q = q.filter(db.or_(Job.title.like(f"%{v}%"), Job.skills.like(f"%{v}%"), Job.description.like(f"%{v}%")))
    if v := request.args.get("location"): q = q.filter(Job.location == v)
    if v := request.args.get("job_type"): q = q.filter(Job.job_type == v)
    p = q.order_by(Job.posted.desc()).paginate(page=request.args.get("page", 1, int), per_page=10, error_out=False)
    return jsonify(jobs=[j.to_dict() for j in p.items], page=p.page, pages=p.pages, total=p.total)


@app.get("/jobs/<int:jid>")
def job_detail(jid): return jsonify(db.get_or_404(Job, jid).to_dict())


@app.post("/jobs/<int:jid>/save")
@login_required()
def save_job(jid):
    db.get_or_404(Job, jid)
    if SavedJob.query.filter_by(user_id=session["user_id"], job_id=jid).first():
        return jsonify(error="Already saved"), 409
    db.session.add(SavedJob(user_id=session["user_id"], job_id=jid)); db.session.commit()
    return jsonify(message="Saved"), 201


@app.post("/jobs/<int:jid>/apply")
@login_required()
def apply(jid):
    db.get_or_404(Job, jid)
    if Application.query.filter_by(user_id=session["user_id"], job_id=jid).first():
        return jsonify(error="Already applied"), 409
    db.session.add(Application(user_id=session["user_id"], job_id=jid)); db.session.commit()
    return jsonify(message="Applied"), 201


@app.get("/applications")
@login_required()
def my_applications():
    rows = Application.query.filter_by(user_id=session["user_id"]).all()
    return jsonify([dict(job_id=a.job_id, status=a.status) for a in rows])


@app.get("/recommendations")
@login_required()
def recommendations():
    u = db.session.get(User, session["user_id"])
    user = dict(skills=split(u.skills), text=u.bio or "", exp=u.experience_years or 0,
                locations=split(u.locations), roles=split(u.roles), job_type=u.job_type)
    if not user["skills"] and not user["text"] and not user["roles"]:
        return jsonify(message="Complete your profile to get recommendations", results=[])
    try:
        res = recommend(user, [j.to_dict() for j in Job.query.filter_by(active=True)])
    except Exception:
        app.logger.exception("Recommendation failure"); return jsonify(error="Could not generate recommendations"), 500
    return jsonify(results=res[:10])


@app.post("/admin/jobs")
@login_required("admin")
def admin_add_job():
    d = request.get_json() or {}
    if not d.get("title"): return jsonify(error="title required"), 400
    j = Job(**{k: d.get(k) for k in ("title", "company", "description", "location", "job_type", "salary", "skills")},
            exp_min=d.get("exp_min", 0))
    db.session.add(j); db.session.commit()
    return jsonify(j.to_dict()), 201


@app.patch("/admin/applications/<int:aid>")
@login_required("admin")
def admin_status(aid):
    a = db.get_or_404(Application, aid); a.status = (request.get_json() or {}).get("status", a.status)
    db.session.commit(); return jsonify(message="Updated")


@app.get("/admin/stats")
@login_required("admin")
def admin_stats():
    return jsonify(users=User.query.count(), active_jobs=Job.query.filter_by(active=True).count(),
                   applications=Application.query.count(), saved_jobs=SavedJob.query.count())


@app.get("/")
def home(): return app.send_static_file("index.html")


@app.get("/skills/suggest")
def suggest():
    q = (request.args.get("q") or "").strip().lower()[:30]
    if not q: return jsonify([])
    starts = [s.name for s in Skill.query.filter(Skill.name.like(f"{q}%")).order_by(Skill.name).limit(20)]
    rest = [s.name for s in Skill.query.filter(Skill.name.like(f"%{q}%")).order_by(Skill.name).limit(40)
            if s.name not in starts]
    return jsonify((starts + rest)[:20])


@app.post("/match")
def live_match():
    """Public live matching: works without login, computed from stored jobs."""
    d = request.get_json() or {}
    user = dict(skills=d.get("skills", []), text="", exp=float(d.get("exp") or 0), locations=[d["location"]] if d.get("location") else [],
                roles=[d["roles"]] if d.get("roles") else [], job_type=d.get("job_type") or "")
    hours = 24 if int(d.get("within_hours") or 72) <= 24 else 72          # only 24h or 3-day windows
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    jobs = Job.query.filter(Job.active.is_(True), Job.posted >= cutoff).all()
    res = recommend(user, [j.to_dict() for j in jobs])
    return jsonify(results=[r for r in res if r["match"] >= 20][:20])


def extract_text(data, ext):
    if ext == ".pdf":
        if not data.startswith(b"%PDF"): raise ValueError("Not a real PDF")
        from pypdf import PdfReader
        return " ".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages[:10])
    return data.decode("utf-8", "ignore")


def extract_profile(text):
    low = text.lower()
    skills = [s for s in LANGS if re.search(r"(?<![a-z0-9+#])" + re.escape(s.lower()) + r"(?![a-z0-9+#])", low)]
    yrs = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\+?\s*(?:years|yrs)", low)]
    locs = [l for l in ("Hyderabad", "Bangalore", "Chennai", "Remote") if l.lower() in low]
    return skills, (max(yrs) if yrs else 0), locs


@app.post("/resume/upload")
def resume_upload():
    """PDF/TXT resume -> extracted skills -> jobs from TRUSTED companies posted in last 24h/3d.
    The file is processed in memory and never saved to disk."""
    f = request.files.get("resume")
    if not f or not f.filename: return jsonify(error="No file uploaded"), 400
    ext = os.path.splitext(f.filename.lower())[1]
    if ext not in (".pdf", ".txt"): return jsonify(error="Only PDF or TXT files are allowed"), 400
    data = f.read(2 * 1024 * 1024 + 1)
    if len(data) > 2 * 1024 * 1024: return jsonify(error="File too large (max 2 MB)"), 413
    try:
        text = extract_text(data, ext)
    except Exception:
        app.logger.exception("Resume parse failed"); return jsonify(error="Could not read this file"), 422
    if len(text.strip()) < 30: return jsonify(error="No readable text found (scanned PDFs are not supported)"), 422
    skills, exp, locs = extract_profile(text)
    hours = 24 if int(request.form.get("within_hours") or 72) <= 24 else 72
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    jobs = Job.query.filter(Job.active.is_(True), Job.trusted.is_(True), Job.posted >= cutoff).all()
    user = dict(skills=skills, text=text[:5000], exp=exp, locations=locs[:1], roles=[], job_type="")
    res = [r for r in recommend(user, [j.to_dict() for j in jobs]) if r["match"] >= 20][:20]
    return jsonify(profile=dict(skills=skills, exp=exp, location=locs[0] if locs else ""), results=res)


@app.errorhandler(413)
def e413(e): return jsonify(error="File too large (max 3 MB)"), 413


@app.errorhandler(404)
def e404(e): return jsonify(error="Not found"), 404
@app.errorhandler(500)
def e500(e): app.logger.exception("Server error"); return jsonify(error="Internal server error"), 500


SEED = [
    ("Python Backend Developer", "ABC Technologies", "Build REST APIs with Flask and SQL databases.", "Hyderabad", "Full-time", 0, "5-8 LPA", "Python,Flask,SQL,REST API,Git"),
    ("Frontend Developer", "PixelWorks", "Build responsive UIs with React and CSS.", "Bangalore", "Full-time", 1, "6-10 LPA", "React,JavaScript,CSS,HTML,Git"),
    ("Data Analyst", "InsightIQ", "Analyse data using SQL, Pandas and dashboards.", "Hyderabad", "Full-time", 1, "5-9 LPA", "Python,SQL,Pandas,Excel"),
    ("DevOps Engineer", "CloudNine", "Automate CI/CD and manage AWS infrastructure.", "Remote", "Full-time", 2, "9-15 LPA", "Docker,AWS,Linux,Git,Python"),
    ("Full Stack Developer", "StackLoop", "Work on Flask backends and JavaScript frontends.", "Chennai", "Full-time", 1, "7-12 LPA", "Python,Flask,JavaScript,SQL,Docker"),
    ("Java Backend Developer", "FinServe", "Build Spring Boot microservices for payments.", "Bangalore", "Full-time", 2, "10-16 LPA", "Java,Spring Boot,SQL,Docker,Git"),
    ("React Native Developer", "AppForge", "Ship mobile apps with React and TypeScript.", "Remote", "Full-time", 1, "8-13 LPA", "React,TypeScript,JavaScript,Git"),
    ("PHP Web Developer", "WebNest", "Maintain PHP and MySQL websites.", "Chennai", "Full-time", 0, "3-5 LPA", "PHP,MySQL,HTML,CSS,JavaScript"),
    ("Go Platform Engineer", "ScaleOps", "Build Go services on Kubernetes.", "Hyderabad", "Full-time", 3, "16-26 LPA", "Go,Kubernetes,Docker,Linux,AWS"),
    ("ML Engineer Intern", "NeuralNest", "Assist in building scikit-learn models.", "Remote", "Internship", 0, "2-3 LPA", "Python,Scikit-learn,Pandas,NumPy"),
]


TRUSTED = {"ABC Technologies", "InsightIQ", "CloudNine", "FinServe", "ScaleOps", "NeuralNest"}


def init_db():
    db.create_all()
    for n in LANGS:
        if not Skill.query.filter_by(name=n).first(): db.session.add(Skill(name=n))
    if not Job.query.first():
        for n, (t, c, d, l, jt, e, s, sk) in enumerate(SEED):
            db.session.add(Job(title=t, company=c, trusted=c in TRUSTED, description=d, location=l, job_type=jt, exp_min=e, salary=s, skills=sk,
                           posted=datetime.utcnow() - timedelta(hours=[2, 10, 20, 30, 50, 70, 90, 120, 5, 40][n % 10])))
    if not User.query.filter_by(role="admin").first():
        pw = os.getenv("ADMIN_PASSWORD", "ChangeMe123!")
        db.session.add(User(name="Admin", email="admin@careermatch.local", password_hash=generate_password_hash(pw), role="admin"))
    db.session.commit()


if __name__ == "__main__":
    with app.app_context(): init_db()
    app.run(debug=os.getenv("FLASK_ENV") != "production")   # production: gunicorn app:app
