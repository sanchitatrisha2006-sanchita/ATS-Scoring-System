"""
AI-Powered ATS Scoring System
------------------------------
Main Flask application. Handles:
- User authentication (signup/login/logout)
- Resume upload + Job description input
- ATS scoring using scoring_engine.py
- Dashboard with score history + chart
"""

import os
import io
import re
import base64
import matplotlib
matplotlib.use("Agg")  # no GUI backend needed on server
import matplotlib.pyplot as plt

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import (
    LoginManager, login_user, login_required, logout_user, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from models import db, User, ScoreRecord
from file_utils import allowed_file, extract_text_from_file
from scoring_engine import analyze_resume, generate_suggestions, COMMON_SKILLS, has_word as _has_word

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
INSTANCE_FOLDER = os.path.join(BASE_DIR, "instance")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(INSTANCE_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this-secret-key-in-production"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'ats.db')}"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB max upload
RESUME_MAX_CHARS = 100000  # a normal resume has far less text; very long text is rejected
JD_MAX_CHARS = 50000

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ---------------------------------------------------------------------------
# Auth Routes
# ---------------------------------------------------------------------------

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not username or not email or not password:
            flash("All fields are required.", "danger")
            return redirect(url_for("signup"))

        if " " in email or "@" not in email or "." not in email.rsplit("@", 1)[-1]:
            flash("Enter a valid email address.", "danger")
            return redirect(url_for("signup"))

        if len(password) < 6 or not password.strip():
            flash("Password must be at least 6 characters.", "danger")
            return redirect(url_for("signup"))

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash("Username or email already exists.", "danger")
            return redirect(url_for("signup"))

        new_user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
        )
        db.session.add(new_user)
        db.session.commit()

        flash("Account created successfully! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username or password.", "danger")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Helper: Resume validation
# ---------------------------------------------------------------------------

DEGREE_KEYWORDS = [
    "bachelor", "master", "b.tech", "btech", "m.tech", "mtech", "b.e", "bca", "mca",
    "b.sc", "bsc", "m.sc", "msc", "mba", "b.com", "bcom", "diploma", "phd",
    "b.a", "m.a", "b.ed", "m.ed", "bba", "bbm", "m.com", "mbbs", "b.pharm", "m.pharm",
    "b.arch", "llb", "llm", "polytechnic", "hsc", "ssc",
]

# Typical resume section headings
SECTION_WORDS = [
    "education", "experience", "skills", "projects", "objective", "summary", "certifications",
    "internship", "qualification", "achievements", "references", "declaration",
]


def looks_like_resume(text: str) -> bool:
    """Simple heuristic: a resume has a known skill or degree, or at least two typical section headings."""
    t = text.lower()
    if any(_has_word(t, s) for s in COMMON_SKILLS) or any(_has_word(t, d) for d in DEGREE_KEYWORDS):
        return True
    return sum(1 for w in SECTION_WORDS if _has_word(t, w)) >= 2


def _remove_file(path: str) -> None:
    """Delete an uploaded file that was rejected, so unused resumes do not pile up."""
    try:
        os.remove(path)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Core App Routes
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    records = (
        ScoreRecord.query.filter_by(user_id=current_user.id)
        .order_by(ScoreRecord.created_at.desc())
        .all()
    )

    chart_base64 = None
    if records:
        try:
            chart_base64 = generate_score_chart(records)
        except Exception:
            chart_base64 = None  # the history table is still shown if the chart fails

    return render_template("dashboard.html", records=records, chart_base64=chart_base64)


@app.route("/analyze", methods=["GET", "POST"])
@login_required
def analyze():
    if request.method == "POST":
        job_title = request.form.get("job_title", "").strip()
        jd_text = request.form.get("job_description", "").strip()
        resume_file = request.files.get("resume")

        if not jd_text or not resume_file or resume_file.filename == "":
            flash("Please provide both a resume file and a job description.", "danger")
            return redirect(url_for("analyze"))

        if len(jd_text) > JD_MAX_CHARS:
            flash("The job description is too long. Please paste only the important part.", "danger")
            return redirect(url_for("analyze"))

        if not allowed_file(resume_file.filename):
            flash("Only PDF, DOCX, and TXT files are supported.", "danger")
            return redirect(url_for("analyze"))

        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        safe_name = secure_filename(f"{current_user.id}_{resume_file.filename}")
        root, ext = os.path.splitext(safe_name)
        filename = root[:80] + ext  # keep the stored file name short
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        resume_file.save(filepath)

        resume_text = extract_text_from_file(filepath)

        if not resume_text.strip():
            _remove_file(filepath)
            flash("Could not extract text from the uploaded resume. Try a different file.", "danger")
            return redirect(url_for("analyze"))

        if len(resume_text) > RESUME_MAX_CHARS:
            _remove_file(filepath)
            flash("The resume is too long to analyze. Please upload a normal resume (a few pages).", "danger")
            return redirect(url_for("analyze"))

        if not looks_like_resume(resume_text):
            _remove_file(filepath)
            flash("This doesn't look like a resume (no skills, degree or resume headings found). Please upload a valid resume.", "danger")
            return redirect(url_for("analyze"))

        result = analyze_resume(resume_text, jd_text)

        record = ScoreRecord(
            user_id=current_user.id,
            resume_filename=resume_file.filename[:255],
            job_title=job_title or "Untitled Job",
            score=result["score"],
            missing_keywords=", ".join(result["missing_keywords"]),
        )
        db.session.add(record)
        db.session.commit()

        # Redirect after POST: refreshing the result page does not save the analysis again
        return redirect(url_for("result", record_id=record.id))

    return render_template("analyze.html")


@app.route("/result/<int:record_id>")
@login_required
def result(record_id):
    record = ScoreRecord.query.filter_by(id=record_id, user_id=current_user.id).first_or_404()
    missing = [k for k in (record.missing_keywords or "").split(", ") if k]
    result_data = {
        "score": record.score,
        "missing_keywords": missing,
        "suggestions": generate_suggestions(missing, record.score),
    }
    return render_template("result.html", result=result_data, job_title=record.job_title)


# ---------------------------------------------------------------------------
# Helper: Chart generation
# ---------------------------------------------------------------------------

def generate_score_chart(records):
    """Bar chart of the latest 10 scores (oldest to newest), returned as a base64 PNG string."""
    latest = list(reversed(records[:10]))  # records are newest first
    # '$' would be read by matplotlib as math text, so it is escaped
    labels = [(r.job_title or "")[:15].replace("$", "\\$") for r in latest]
    scores = [r.score for r in latest]
    positions = list(range(len(scores)))  # numbers, so repeated job titles still get their own bar

    fig, ax = plt.subplots(figsize=(7, 4))
    try:
        bars = ax.bar(positions, scores, color="#4f46e5")
        ax.set_xticks(positions)
        ax.set_xticklabels(labels, rotation=30, ha="right")
        ax.set_ylabel("ATS Score (%)")
        ax.set_title("Your Resume Score History")
        ax.set_ylim(0, 100)

        for bar, score in zip(bars, scores):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                    f"{score:.0f}", ha="center", fontsize=9)

        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("utf-8")
    finally:
        plt.close(fig)


# ---------------------------------------------------------------------------
# App Entry
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
