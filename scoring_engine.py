"""
ATS Scoring Engine
------------------
This module does the actual "AI" work of the project:
1. Extract text from resumes (PDF / DOCX / TXT)
2. Clean and tokenize text using spaCy (remove stopwords, punctuation, lemmatize)
3. Compare resume text vs job description using TF-IDF + Cosine Similarity
4. Extract important keywords from the JD and check which ones are missing from resume
5. Return a final score (0-100) + list of missing keywords + suggestions
"""

import re
import spacy
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Load spaCy's small English model once (reused for every request)
nlp = spacy.load("en_core_web_sm")

# A basic skill/keyword dictionary — you can expand this list anytime.
COMMON_SKILLS = [
    "python", "java", "c++", "javascript", "sql", "html", "css", "flask",
    "django", "react", "node.js", "machine learning", "deep learning",
    "nlp", "data analysis", "excel", "power bi", "tableau", "git", "github",
    "aws", "azure", "docker", "kubernetes", "linux", "communication",
    "teamwork", "leadership", "problem solving", "project management",
    "spacy", "scikit-learn", "tensorflow", "pytorch", "pandas", "numpy",
    "rest api", "mysql", "mongodb", "agile", "scrum",
]


# Words that carry no skill information when they are the only words of a noun phrase
GENERIC_WORDS = {
    "role", "job", "title", "responsibilities", "responsibility", "requirements", "requirement",
    "skills", "skill", "experience", "team", "company", "candidate", "position", "knowledge",
    "ability", "work", "year", "years", "description", "overview",
}


def has_word(text: str, word: str) -> bool:
    """True if `word` appears as a whole word (so 'java' is not found inside 'javascript',
    'excel' not inside 'excellent', 'git' not inside 'digital')."""
    return re.search(r"(?<![a-z0-9+#.])" + re.escape(word) + r"(?![a-z0-9+#])", text) is not None


def clean_text(text: str) -> str:
    """Lowercase, remove extra symbols/whitespace, and lemmatize using spaCy."""
    text = text.lower()
    text = re.sub(r"[^a-zA-Z0-9+.\s]", " ", text)  # keep + and . for skills like C++ / node.js
    text = re.sub(r"\s+", " ", text).strip()

    doc = nlp(text)
    tokens = [
        token.lemma_
        for token in doc
        if not token.is_stop and not token.is_punct and token.text.strip() != ""
    ]
    return " ".join(tokens)


def extract_keywords(jd_text: str, top_n: int = 20):
    """
    Extract the most relevant keywords/skills from the job description.
    Combines: (a) known skills dictionary matches (all of them), (b) clean noun phrases from spaCy
    to fill the remaining places up to top_n.
    """
    jd_lower = re.sub(r"\s+", " ", jd_text.lower())
    found_skills = [skill for skill in COMMON_SKILLS if has_word(jd_lower, skill)]

    doc = nlp(jd_text)
    phrases = []
    for chunk in doc.noun_chunks:
        if "\n" in chunk.text or chunk.root.is_stop:
            continue  # skip phrases that run across lines
        words = [t.text.lower() for t in chunk if t.is_alpha and not t.is_stop]
        phrase = " ".join(words)
        if not (3 <= len(phrase) <= 30):
            continue
        if all(w in GENERIC_WORDS for w in words):
            continue  # e.g. "the role", "years", "job title"
        if phrase in found_skills or phrase in phrases:
            continue
        phrases.append(phrase)

    return found_skills + phrases[: max(0, top_n - len(found_skills))]


def missing_keywords(resume_text: str, keywords: list):
    """Return keywords from the JD that do NOT appear (as whole words) in the resume text."""
    resume_lower = re.sub(r"\s+", " ", resume_text.lower())
    return [kw for kw in keywords if not has_word(resume_lower, kw)]


def calculate_similarity_score(resume_text: str, jd_text: str) -> float:
    """
    Core ATS score using TF-IDF vectorization + Cosine Similarity.
    Returns a percentage score between 0 and 100.
    """
    cleaned_resume = clean_text(resume_text)
    cleaned_jd = clean_text(jd_text)

    if not cleaned_resume.strip() or not cleaned_jd.strip():
        return 0.0

    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform([cleaned_resume, cleaned_jd])
    similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]

    score = round(similarity * 100, 2)
    return score


def generate_suggestions(missing_kw: list, score: float) -> list:
    """Generate simple human-readable feedback based on the score and missing keywords."""
    suggestions = []

    if score < 40:
        suggestions.append("Your resume has low overlap with this job description. Consider tailoring it significantly.")
    elif score < 70:
        suggestions.append("Decent match, but there's room to improve keyword alignment.")
    else:
        suggestions.append("Great match! Your resume aligns well with this job description.")

    if missing_kw:
        top_missing = ", ".join(missing_kw[:8])
        suggestions.append(f"Consider adding these missing keywords/skills if relevant: {top_missing}.")

    suggestions.append("Use standard section headings (Experience, Education, Skills) so ATS parsers can read them correctly.")
    suggestions.append("Avoid images, tables, or columns in your resume — many ATS systems fail to parse them.")

    return suggestions


def analyze_resume(resume_text: str, jd_text: str) -> dict:
    """
    Main entry point used by the Flask app.
    Returns a dictionary with score, missing keywords, and suggestions.
    """
    score = calculate_similarity_score(resume_text, jd_text)
    keywords = extract_keywords(jd_text)
    missing = missing_keywords(resume_text, keywords)
    suggestions = generate_suggestions(missing, score)

    return {
        "score": score,
        "keywords_found_in_jd": keywords,
        "missing_keywords": missing,
        "suggestions": suggestions,
    }
