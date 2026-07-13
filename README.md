# AcademIQ — Academic Integrity & Anomaly Detection Agent

> Powered by **IBM Watsonx.ai** · **Granite Models** · **Flask**

An AI-powered web application that helps educators analyse academic submissions for stylometric anomalies, AI-generated content signals, cross-submission similarity, and student writing baseline profiles.

---

## 📁 Project Structure

```
academiq/
├── app.py                  # Flask backend + Watsonx.ai integration
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
├── .env                    # Your credentials (never commit this)
├── README.md
├── templates/
│   └── index.html          # Single-page frontend
└── static/
    ├── css/
    │   └── style.css       # Custom styles
    └── js/
        └── app.js          # Frontend logic
```

---

## ⚡ Quick Start

### 1 · Clone / download the project

```bash
git clone https://github.com/your-org/academiq.git
cd academiq
```

### 2 · Create a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3 · Install dependencies

```bash
pip install -r requirements.txt
```

### 4 · Configure credentials

```bash
cp .env.example .env
```

Open `.env` and fill in:

| Variable | Description |
|---|---|
| `IBM_API_KEY` | Your IBM Cloud API key |
| `WATSONX_PROJECT_ID` | Your Watsonx.ai project ID |
| `WATSONX_URL` | Regional endpoint (default: `us-south`) |
| `FLASK_SECRET_KEY` | A long random string for session security |
| `GRANITE_MODEL_ID` | Model to use (default: `ibm/granite-3-8b-instruct`) |

#### How to get IBM credentials

1. Log in to [IBM Cloud Console](https://cloud.ibm.com)
2. Go to **Manage → Access (IAM) → API Keys** → Create API key
3. Open [IBM Watsonx.ai](https://dataplatform.cloud.ibm.com)
4. Create or open a **Project** → copy the **Project ID** from Settings

### 5 · Run the application

```bash
python app.py
```

Open your browser at **http://localhost:5000**

---

## 🤖 Customising the Agent

All agent behaviour is controlled by the `AGENT_INSTRUCTIONS` dictionary at the top of [`app.py`](app.py). No code changes are required elsewhere.

```python
AGENT_INSTRUCTIONS = {
    # Identity
    "name":        "AcademIQ",
    "role":        "Academic Integrity Specialist",
    "institution": "Your University Name",

    # Tone — change to be more/less formal, lenient, etc.
    "tone": "professional yet supportive. Avoid accusatory language...",

    # Detection focus — add or remove specialisations
    "detection_focus": [
        "stylometric anomalies",
        "AI-generated text patterns",
        ...
    ],

    # Safety rules — ethical guardrails
    "safety_rules": [
        "Never declare a student guilty...",
        ...
    ],

    # Local academic context
    "academic_context": {
        "grading_scale":      "A–F (US standard)",
        "citation_styles":    ["APA 7th", "MLA 9th"],
        "integrity_policy_url": "https://your-institution.edu/integrity",
        "escalation_contact": "integrity@your-institution.edu",
        "ai_tool_policy":     "Students must disclose AI tool usage...",
    },
}
```

---

## 🔌 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET`  | `/` | Serve the web UI |
| `GET`  | `/api/health` | System status |
| `POST` | `/api/chat` | Chat with the agent |
| `POST` | `/api/analyze` | Full submission analysis |
| `POST` | `/api/similarity` | Compare two submissions |
| `POST` | `/api/profile` | Build student baseline profile |

### POST `/api/chat`

```json
{
  "message": "What are common AI text signals?",
  "history": []
}
```

### POST `/api/analyze`

```json
{
  "text": "Full submission text here...",
  "student_name": "Jane Smith",
  "assignment_name": "Essay 3",
  "baseline_text": "Prior verified work (optional)"
}
```

### POST `/api/similarity`

```json
{
  "text_a": "First submission...",
  "text_b": "Second submission...",
  "label_a": "Student A",
  "label_b": "Student B"
}
```

### POST `/api/profile`

```json
{
  "student_name": "Alex Johnson",
  "submissions": ["Text 1...", "Text 2...", "Text 3..."]
}
```

---

## 🧪 Features

| Feature | Description |
|---|---|
| **Chat Interface** | Conversational AI powered by Granite |
| **Stylometric Analysis** | 12+ writing features extracted locally |
| **AI Detection** | Burstiness, phrase density, structural uniformity |
| **Similarity Check** | TF-IDF cosine similarity with risk scoring |
| **Student Profiling** | Baseline writing profile from multiple submissions |
| **Dashboard** | Session stats, log, risk distribution chart |
| **Dark Mode** | Persistent preference stored in localStorage |
| **Mobile Responsive** | Bootstrap 5.3 grid, works on all screen sizes |

---

## 🚀 Production Deployment

### Option A — Gunicorn (recommended for Linux/macOS)

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Option B — Docker

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "app:app"]
```

```bash
docker build -t academiq .
docker run -p 5000:5000 --env-file .env academiq
```

### Option C — IBM Code Engine

```bash
ibmcloud ce application create \
  --name academiq \
  --image icr.io/your-namespace/academiq:latest \
  --port 5000 \
  --env-from-secret academiq-secrets
```

### Option D — Railway / Render / Heroku

1. Push code to GitHub
2. Connect repo in platform dashboard
3. Set environment variables from `.env.example`
4. Deploy

### Nginx reverse proxy (optional)

```nginx
server {
    listen 80;
    server_name your-domain.com;
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 🔒 Security Checklist

- [ ] Set a strong `FLASK_SECRET_KEY` (32+ random characters)
- [ ] Set `FLASK_ENV=production` in production
- [ ] Never commit `.env` to version control
- [ ] Add `.env` to `.gitignore`
- [ ] Use HTTPS behind a reverse proxy
- [ ] Limit request body size with `MAX_CONTENT_LENGTH`

---

## 🧩 Granite Model Options

| Model ID | Best for |
|---|---|
| `ibm/granite-3-8b-instruct` | Default — best balance |
| `ibm/granite-3-2b-instruct` | Faster, lower cost |
| `ibm/granite-3-3b-a800m-instruct` | MoE, efficient |

Change via `GRANITE_MODEL_ID` in `.env`.

---

## 📜 Ethical Use Statement

This tool provides **probabilistic analysis** for educator support. It does **not** render definitive verdicts. All flagged submissions must undergo human review before any disciplinary action. The agent is designed to:

- Use supportive, non-accusatory language
- Acknowledge innocent explanations for anomalies
- Protect student privacy
- Recommend escalation to qualified humans

---

## 📄 Licence

MIT — See `LICENSE` file.
