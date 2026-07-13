"""
AcademIQ - Academic Integrity & Anomaly Detection Agent
Powered by IBM Watsonx.ai + Granite Models
Flask Backend - app.py
"""

import os
import re
import json
import math
import hashlib
import datetime
from collections import Counter
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS

# ── Optional NLP deps (gracefully degraded if absent) ─────────────────────
try:
    import nltk
    from nltk.tokenize import word_tokenize, sent_tokenize
    from nltk.corpus import stopwords
    nltk.download("punkt", quiet=True)
    nltk.download("punkt_tab", quiet=True)
    nltk.download("stopwords", quiet=True)
    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False

try:
    import textstat
    TEXTSTAT_AVAILABLE = True
except ImportError:
    TEXTSTAT_AVAILABLE = False

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

# IBM Watsonx
from ibm_watsonx_ai import Credentials
from ibm_watsonx_ai.foundation_models import ModelInference
from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams

load_dotenv()

# ══════════════════════════════════════════════════════════════════════════════
#  AGENT INSTRUCTIONS — Customise agent behaviour here
# ══════════════════════════════════════════════════════════════════════════════
AGENT_INSTRUCTIONS = {
    # ── Core identity ────────────────────────────────────────────────────────
    "name": "AcademIQ",
    "role": "Academic Integrity & Anomaly Detection Specialist",
    "institution": "University Academic Integrity Office",

    # ── Tone & communication style ────────────────────────────────────────────
    "tone": (
        "professional yet supportive. Avoid accusatory language. "
        "Frame findings as 'areas requiring review' rather than definitive judgements. "
        "Always suggest next steps for the educator."
    ),

    # ── Detection specialisations ─────────────────────────────────────────────
    "detection_focus": [
        "stylometric anomalies (vocabulary shift, sentence complexity changes)",
        "AI-generated text patterns (perplexity, burstiness, uniform structure)",
        "structural inconsistencies (citation density, paragraph length variance)",
        "sudden improvement anomalies vs established student baseline",
        "cross-submission similarity and contract-cheating signals",
    ],

    # ── Safety & ethical rules ────────────────────────────────────────────────
    "safety_rules": [
        "Never declare a student guilty; always use probabilistic language.",
        "Recommend human review for any flagged submission.",
        "Protect student privacy — never store or repeat full submission text.",
        "Acknowledge that anomalies can have legitimate explanations (tutoring, illness, etc.).",
        "Provide balanced analysis that also notes positive aspects of the work.",
    ],

    # ── Local academic context ────────────────────────────────────────────────
    "academic_context": {
        "grading_scale": "A–F (US standard)",
        "citation_styles": ["APA 7th", "MLA 9th", "Chicago 17th"],
        "integrity_policy_url": "https://your-institution.edu/integrity",
        "escalation_contact": "integrity@your-institution.edu",
        "ai_tool_policy": (
            "Students must disclose AI tool usage; undisclosed use is a violation."
        ),
    },

    # ── Response formatting ───────────────────────────────────────────────────
    "response_format": {
        "use_sections": True,
        "include_risk_score": True,
        "include_recommendations": True,
        "max_bullet_points": 6,
    },
}

# ══════════════════════════════════════════════════════════════════════════════
#  Flask App Setup
# ══════════════════════════════════════════════════════════════════════════════
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-in-prod")
CORS(app)

# ══════════════════════════════════════════════════════════════════════════════
#  Watsonx.ai Model Initialisation
# ══════════════════════════════════════════════════════════════════════════════
def get_watsonx_model():
    """Initialise and return the Granite model inference object."""
    # Standard IBM Cloud (IAM) authentication — apikey only, no username/version
    credentials = {
        "url": os.getenv("WATSONX_URL", "https://au-syd.ml.cloud.ibm.com"),
        "apikey": os.getenv("IBM_API_KEY", "LneTtNeb1hWfBfwcX8VXjWuOI2LETauGGGH-5wukysmC"),
    }
    
    params = {
        GenParams.MAX_NEW_TOKENS: int(os.getenv("GRANITE_MAX_TOKENS", 2048)),
        GenParams.TEMPERATURE: float(os.getenv("GRANITE_TEMPERATURE", 0.3)),
        GenParams.TOP_P: float(os.getenv("GRANITE_TOP_P", 0.9)),
        GenParams.REPETITION_PENALTY: 1.1,
        GenParams.STOP_SEQUENCES: ["<|endoftext|>"],
    }
    
    return ModelInference(
        model_id=os.getenv("GRANITE_MODEL_ID", "meta-llama/llama-3-3-70b-instruct"),
        credentials=credentials,
        project_id=os.getenv("WATSONX_PROJECT_ID", "8289e4f8-9138-44ea-9864-e260414cc1a4"),
        params=params,
    )
# ══════════════════════════════════════════════════════════════════════════════
#  Prompt Builder
# ══════════════════════════════════════════════════════════════════════════════
def build_system_prompt() -> str:
    """Construct the system prompt from AGENT_INSTRUCTIONS."""
    ai = AGENT_INSTRUCTIONS
    safety = "\n".join(f"  • {r}" for r in ai["safety_rules"])
    focus = "\n".join(f"  • {f}" for f in ai["detection_focus"])
    ctx = ai["academic_context"]
    return f"""You are {ai['name']}, an {ai['role']} at {ai['institution']}.

COMMUNICATION STYLE
Your tone is {ai['tone']}

DETECTION SPECIALISATIONS
{focus}

SAFETY & ETHICAL RULES (always follow)
{safety}

ACADEMIC CONTEXT
- Grading scale: {ctx['grading_scale']}
- Citation styles in use: {', '.join(ctx['citation_styles'])}
- AI tool policy: {ctx['ai_tool_policy']}
- Escalation contact: {ctx['escalation_contact']}

RESPONSE FORMATTING
- Use clear section headers (##) for structured responses.
- Always include a **Risk Level** (Low / Medium / High / Critical) when analysing submissions.
- End every analysis with a **Recommended Actions** section.
- Keep bullet lists to max {ai['response_format']['max_bullet_points']} items per section.
- Be concise; educators are busy professionals.
"""

def build_chat_prompt(system: str, history: list, user_message: str) -> str:
    """Build the full prompt string for Granite instruct format."""
    prompt = f"<|system|>\n{system}\n"
    for turn in history[-6:]:           # keep last 6 turns for context window
        role = turn.get("role", "user")
        content = turn.get("content", "")
        prompt += f"<|{role}|>\n{content}\n"
    prompt += f"<|user|>\n{user_message}\n<|assistant|>\n"
    return prompt

# ══════════════════════════════════════════════════════════════════════════════
#  Stylometric & Text Analysis Helpers
# ══════════════════════════════════════════════════════════════════════════════
def compute_stylometric_features(text: str) -> dict:
    """Return a dict of stylometric feature values for the given text."""
    if not text or not text.strip():
        return {}

    words = re.findall(r"\b[a-zA-Z']+\b", text.lower())
    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    word_count = len(words)
    sent_count = max(len(sentences), 1)
    para_count = max(len(paragraphs), 1)

    # Vocabulary richness (Type-Token Ratio)
    unique_words = set(words)
    ttr = round(len(unique_words) / max(word_count, 1), 4)

    # Average sentence length
    avg_sent_len = round(word_count / sent_count, 2)

    # Sentence length variance
    sent_lengths = [len(re.findall(r"\b\w+\b", s)) for s in sentences]
    mean_sl = sum(sent_lengths) / max(len(sent_lengths), 1)
    variance = sum((l - mean_sl) ** 2 for l in sent_lengths) / max(len(sent_lengths), 1)
    sent_len_stddev = round(math.sqrt(variance), 2)

    # Punctuation density
    punct_count = len(re.findall(r"[,;:\"'()\[\]{}\-—]", text))
    punct_density = round(punct_count / max(word_count, 1), 4)

    # Passive voice proxy (crude heuristic)
    passive_matches = len(re.findall(
        r"\b(is|are|was|were|been|being)\s+\w+ed\b", text, re.IGNORECASE
    ))
    passive_ratio = round(passive_matches / max(sent_count, 1), 4)

    # Transition word density
    transitions = [
        "however", "therefore", "furthermore", "moreover", "consequently",
        "nevertheless", "although", "whereas", "thus", "hence", "additionally"
    ]
    trans_count = sum(text.lower().count(t) for t in transitions)
    trans_density = round(trans_count / max(sent_count, 1), 4)

    # Readability
    flesch = 0.0
    if TEXTSTAT_AVAILABLE:
        try:
            flesch = textstat.flesch_reading_ease(text)
        except Exception:
            pass

    # Paragraph length variance
    para_lengths = [len(re.findall(r"\b\w+\b", p)) for p in paragraphs]
    para_mean = sum(para_lengths) / max(len(para_lengths), 1)
    para_var = sum((l - para_mean) ** 2 for l in para_lengths) / max(len(para_lengths), 1)
    para_stddev = round(math.sqrt(para_var), 2)

    return {
        "word_count": word_count,
        "sentence_count": sent_count,
        "paragraph_count": para_count,
        "unique_words": len(unique_words),
        "type_token_ratio": ttr,
        "avg_sentence_length": avg_sent_len,
        "sentence_length_stddev": sent_len_stddev,
        "punctuation_density": punct_density,
        "passive_voice_ratio": passive_ratio,
        "transition_density": trans_density,
        "flesch_reading_ease": round(flesch, 1),
        "paragraph_length_stddev": para_stddev,
    }


def compute_similarity(text_a: str, text_b: str) -> float:
    """Return cosine TF-IDF similarity between two texts (0.0–1.0)."""
    if not SKLEARN_AVAILABLE:
        # Fallback: simple word overlap Jaccard
        set_a = set(re.findall(r"\b[a-z]+\b", text_a.lower()))
        set_b = set(re.findall(r"\b[a-z]+\b", text_b.lower()))
        if not set_a or not set_b:
            return 0.0
        return round(len(set_a & set_b) / len(set_a | set_b), 4)
    try:
        vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        tfidf = vec.fit_transform([text_a, text_b])
        sim = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]
        return round(float(sim), 4)
    except Exception:
        return 0.0


def detect_ai_signals(text: str) -> dict:
    """Heuristic AI-generated text signals (no ML model required)."""
    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

    # Burstiness: human text has high variance in sentence length; AI is more uniform
    lengths = [len(s.split()) for s in sentences]
    if len(lengths) > 1:
        mean_l = sum(lengths) / len(lengths)
        variance = sum((l - mean_l) ** 2 for l in lengths) / len(lengths)
        burstiness = round(math.sqrt(variance) / max(mean_l, 1), 4)
    else:
        burstiness = 0.0

    # Cliché AI phrases
    ai_phrases = [
        "it is important to note", "in conclusion", "in summary", "it is worth noting",
        "as mentioned above", "in the realm of", "delve into", "it is crucial to",
        "play a pivotal role", "a nuanced understanding", "foster a deeper",
        "leverage", "utilize", "facilitate", "paradigm", "synergy",
        "it goes without saying", "needless to say", "comprehensive overview"
    ]
    phrase_hits = [p for p in ai_phrases if p in text.lower()]
    ai_phrase_density = round(len(phrase_hits) / max(len(sentences), 1), 4)

    # Structural uniformity (similar paragraph lengths = AI signal)
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    para_word_counts = [len(p.split()) for p in paragraphs]
    if len(para_word_counts) > 2:
        mean_p = sum(para_word_counts) / len(para_word_counts)
        para_cv = round(
            math.sqrt(sum((c - mean_p) ** 2 for c in para_word_counts) / len(para_word_counts))
            / max(mean_p, 1),
            4,
        )
    else:
        para_cv = 0.5  # neutral when too short

    # Risk scoring
    risk_score = 0
    if burstiness < 0.3:
        risk_score += 30
    if ai_phrase_density > 0.15:
        risk_score += 35
    if para_cv < 0.2:
        risk_score += 20
    risk_score = min(risk_score, 100)

    return {
        "burstiness_score": burstiness,
        "ai_phrase_density": ai_phrase_density,
        "paragraph_uniformity_cv": para_cv,
        "matched_ai_phrases": phrase_hits[:8],
        "ai_risk_score": risk_score,
    }


def risk_level(score: int) -> str:
    if score < 20:
        return "Low"
    if score < 45:
        return "Medium"
    if score < 70:
        return "High"
    return "Critical"

# ══════════════════════════════════════════════════════════════════════════════
#  Routes — Pages
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/")
def index():
    return render_template("index.html", agent=AGENT_INSTRUCTIONS)


@app.route("/dashboard")
def dashboard():
    return render_template("index.html", agent=AGENT_INSTRUCTIONS, page="dashboard")

# ══════════════════════════════════════════════════════════════════════════════
#  API — Chat
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json(force=True)
    user_message = data.get("message", "").strip()
    history = data.get("history", [])

    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    try:
        model = get_watsonx_model()
        system_prompt = build_system_prompt()
        full_prompt = build_chat_prompt(system_prompt, history, user_message)
        response = model.generate_text(prompt=full_prompt)
        assistant_reply = response.strip() if isinstance(response, str) else str(response)
        return jsonify({
            "reply": assistant_reply,
            "agent_name": AGENT_INSTRUCTIONS["name"],
        })
    except Exception as e:
        return jsonify({"error": f"Model error: {str(e)}"}), 500

# ══════════════════════════════════════════════════════════════════════════════
#  API — Full Submission Analysis
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    data = request.get_json(force=True)
    submission_text = data.get("text", "").strip()
    student_name = data.get("student_name", "Anonymous")
    assignment_name = data.get("assignment_name", "Untitled Assignment")
    baseline_text = data.get("baseline_text", "").strip()

    if not submission_text:
        return jsonify({"error": "No submission text provided"}), 400

    # Local feature extraction
    features = compute_stylometric_features(submission_text)
    ai_signals = detect_ai_signals(submission_text)

    baseline_features = {}
    baseline_similarity = None
    if baseline_text:
        baseline_features = compute_stylometric_features(baseline_text)
        baseline_similarity = compute_similarity(submission_text, baseline_text)

    # Build AI analysis prompt
    features_summary = json.dumps(features, indent=2)
    ai_summary = json.dumps(ai_signals, indent=2)
    baseline_note = ""
    if baseline_features:
        baseline_summary = json.dumps(baseline_features, indent=2)
        baseline_note = f"""
STUDENT BASELINE FEATURES (from prior work):
{baseline_summary}

Similarity to current submission: {baseline_similarity}
"""

    analysis_prompt = f"""Analyse the following academic submission for integrity concerns.

STUDENT: {student_name}
ASSIGNMENT: {assignment_name}

STYLOMETRIC FEATURES (computed):
{features_summary}

AI-GENERATION SIGNALS (heuristic):
{ai_summary}
{baseline_note}

Please provide:
## Stylometric Analysis
Interpret the computed features. Flag anything unusual.

## AI-Generation Assessment
Based on the AI signals, assess likelihood of AI-generated content.

## Integrity Risk Summary
Risk Level: [Low/Medium/High/Critical]
Overall risk score: [0-100]

## Positive Observations
What the student did well (if any).

## Recommended Actions
Concrete next steps for the educator (max 5 bullet points).
"""

    try:
        model = get_watsonx_model()
        system_prompt = build_system_prompt()
        full_prompt = build_chat_prompt(system_prompt, [], analysis_prompt)
        ai_analysis = model.generate_text(prompt=full_prompt)
        if not isinstance(ai_analysis, str):
            ai_analysis = str(ai_analysis)
    except Exception as e:
        ai_analysis = f"⚠️ AI analysis unavailable: {str(e)}"

    return jsonify({
        "student_name": student_name,
        "assignment_name": assignment_name,
        "stylometric_features": features,
        "ai_signals": ai_signals,
        "baseline_features": baseline_features,
        "baseline_similarity": baseline_similarity,
        "ai_risk_level": risk_level(ai_signals.get("ai_risk_score", 0)),
        "ai_analysis": ai_analysis,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    })

# ══════════════════════════════════════════════════════════════════════════════
#  API — Similarity Check (two submissions)
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/api/similarity", methods=["POST"])
def api_similarity():
    data = request.get_json(force=True)
    text_a = data.get("text_a", "").strip()
    text_b = data.get("text_b", "").strip()
    label_a = data.get("label_a", "Submission A")
    label_b = data.get("label_b", "Submission B")

    if not text_a or not text_b:
        return jsonify({"error": "Both texts are required"}), 400

    similarity = compute_similarity(text_a, text_b)
    risk = "Low"
    if similarity > 0.85:
        risk = "Critical"
    elif similarity > 0.65:
        risk = "High"
    elif similarity > 0.45:
        risk = "Medium"

    sim_prompt = f"""Two student submissions have been compared.

{label_a} vs {label_b}
Cosine TF-IDF Similarity Score: {similarity} (0=no overlap, 1=identical)
Risk Level: {risk}

Provide a brief professional assessment:
## Similarity Assessment
Interpret the score in an academic integrity context.

## Possible Explanations
List 3-4 possible innocent AND concerning explanations.

## Recommended Actions
"""

    try:
        model = get_watsonx_model()
        system_prompt = build_system_prompt()
        full_prompt = build_chat_prompt(system_prompt, [], sim_prompt)
        ai_assessment = model.generate_text(prompt=full_prompt)
        if not isinstance(ai_assessment, str):
            ai_assessment = str(ai_assessment)
    except Exception as e:
        ai_assessment = f"⚠️ AI assessment unavailable: {str(e)}"

    return jsonify({
        "label_a": label_a,
        "label_b": label_b,
        "similarity_score": similarity,
        "risk_level": risk,
        "ai_assessment": ai_assessment,
    })

# ══════════════════════════════════════════════════════════════════════════════
#  API — Student Profile / Baseline
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/api/profile", methods=["POST"])
def api_profile():
    data = request.get_json(force=True)
    student_name = data.get("student_name", "Anonymous")
    submissions = data.get("submissions", [])   # list of text strings

    if not submissions:
        return jsonify({"error": "At least one submission required"}), 400

    all_features = [compute_stylometric_features(s) for s in submissions if s.strip()]
    if not all_features:
        return jsonify({"error": "No valid submissions to analyse"}), 400

    # Compute aggregate baseline
    keys = all_features[0].keys()
    baseline = {}
    for k in keys:
        vals = [f[k] for f in all_features if k in f and isinstance(f[k], (int, float))]
        if vals:
            baseline[k] = {
                "mean": round(sum(vals) / len(vals), 4),
                "min": round(min(vals), 4),
                "max": round(max(vals), 4),
            }

    profile_prompt = f"""Build a writing baseline profile for student: {student_name}

Number of submissions analysed: {len(all_features)}

Aggregate Stylometric Baseline:
{json.dumps(baseline, indent=2)}

Please provide:
## Student Writing Profile: {student_name}
Describe the student's typical writing style based on the metrics.

## Baseline Norms
Summarise the expected ranges for this student.

## Anomaly Detection Thresholds
What values in future submissions would trigger a review?

## Recommendations for the Student
2-3 constructive writing improvement suggestions.
"""

    try:
        model = get_watsonx_model()
        system_prompt = build_system_prompt()
        full_prompt = build_chat_prompt(system_prompt, [], profile_prompt)
        ai_profile = model.generate_text(prompt=full_prompt)
        if not isinstance(ai_profile, str):
            ai_profile = str(ai_profile)
    except Exception as e:
        ai_profile = f"⚠️ Profile generation unavailable: {str(e)}"

    return jsonify({
        "student_name": student_name,
        "submission_count": len(all_features),
        "baseline": baseline,
        "ai_profile": ai_profile,
    })

# ══════════════════════════════════════════════════════════════════════════════
#  API — Health Check
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/api/health")
def api_health():
    return jsonify({
        "status": "ok",
        "agent": AGENT_INSTRUCTIONS["name"],
        "model": os.getenv("GRANITE_MODEL_ID", "ibm/granite-3-8b-instruct"),
        "nltk": NLTK_AVAILABLE,
        "textstat": TEXTSTAT_AVAILABLE,
        "sklearn": SKLEARN_AVAILABLE,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    })

# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", 5000))
    debug = os.getenv("FLASK_ENV", "development") == "development"
    app.run(host="0.0.0.0", port=port, debug=debug)
