<a id="readme-top"></a>

<!-- BADGES -->
[![GitHub Stars](https://img.shields.io/github/stars/iprashanthvanam/Plagiarism_AI_detection_app?style=for-the-badge&color=f59e0b)](https://github.com/iprashanthvanam/Plagiarism_AI_detection_app/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/iprashanthvanam/Plagiarism_AI_detection_app?style=for-the-badge&color=3b82f6)](https://github.com/iprashanthvanam/Plagiarism_AI_detection_app/network/members)
[![GitHub Issues](https://img.shields.io/github/issues/iprashanthvanam/Plagiarism_AI_detection_app?style=for-the-badge&color=ef4444)](https://github.com/iprashanthvanam/Plagiarism_AI_detection_app/issues)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://reactjs.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?style=for-the-badge&logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io)
[![Deployed on Render](https://img.shields.io/badge/Deployed%20on-Render-46E3B7?style=for-the-badge&logo=render&logoColor=white)](https://plagiarism-analysis-app.onrender.com)

---

<div align="center">

# 🛡️ IntellShield
### AI-Powered Plagiarism & AI Content Detection System

*Detect plagiarism and AI-generated content in academic submissions using a hybrid 6-method NLP ensemble.*

<br/>

[🚀 Live Demo](https://plagiarism-analysis-app.onrender.com) · [🐛 Report Bug](https://github.com/iprashanthvanam/Plagiarism_AI_detection_app/issues/new?labels=bug) · [✨ Request Feature](https://github.com/iprashanthvanam/Plagiarism_AI_detection_app/issues/new?labels=enhancement)

</div>

---

<!-- TABLE OF CONTENTS -->
<details>
  <summary>📑 Table of Contents</summary>
  <ol>
    <li><a href="#about-the-project">About The Project</a></li>
    <li><a href="#screenshots">Screenshots</a></li>
    <li><a href="#key-features">Key Features</a></li>
    <li><a href="#tech-stack">Tech Stack</a></li>
    <li><a href="#system-architecture">System Architecture</a></li>
    <li><a href="#ai-detection-engine">AI Detection Engine (6-Method Ensemble)</a></li>
    <li><a href="#plagiarism-pipeline">Plagiarism Detection Pipeline</a></li>
    <li><a href="#getting-started">Getting Started</a></li>
    <li><a href="#environment-variables">Environment Variables</a></li>
    <li><a href="#database-setup">Database Setup & Seeding</a></li>
    <li><a href="#api-reference">API Reference</a></li>
    <li><a href="#security">Security</a></li>
    <li><a href="#deployment">Deployment</a></li>
    <li><a href="#project-structure">Project Structure</a></li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>

---

## About The Project

Academic institutions face a growing challenge: traditional plagiarism checkers can no longer distinguish between copied content, paraphrased sources, and AI-generated text. Tools like Turnitin are expensive, inaccessible, and not customisable for institutional workflows.

**IntellShield** solves this by combining real-time web search, verbatim n-gram matching, Common Crawl archival search, local document fingerprinting, and a 6-method machine-learning ensemble for AI authorship detection — all in a single, deployable, open-source platform built specifically for TKREC and similar institutions.

**Why IntellShield?**

- ❌ **Old approach:** Single-method plagiarism tools miss paraphrased content and can't detect AI writing
- ✅ **Our approach:** Multi-source plagiarism pipeline + 6-method AI detection ensemble, calibrated against Turnitin's reference behaviour


<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Screenshots

A complete visual walkthrough of every screen in IntellShield.

---

### 🔐 Login Page

<div align="center">
  <img src="Images/Login.png" alt="IntellShield — Login Page" width="860"/>
  <br/><br/>
  <sub><b>Secure login with JWT authentication.</b> Role-based routing sends admins to the Admin Dashboard and students to their personal submission portal.</sub>
</div>

---

### 🛠️ Admin Dashboard

<div align="center">
  <img src="Images/Admin Dashboard.png" alt="IntellShield — Admin Dashboard" width="860"/>
  <br/><br/>
  <sub><b>Institution-wide admin view.</b> Monitor all submitted documents across every student, review scores, and manage the system.</sub>
</div>

---

### 🎓 Student Dashboard

<div align="center">
  <img src="Images/Student Dashboard.png" alt="IntellShield — Student Dashboard" width="860"/>
  <br/><br/>
  <sub><b>Student submission portal.</b> Upload documents, track analysis status in real time, and access all previous reports — all in one place.</sub>
</div>

---

### 🔬 Analysis Page

<div align="center">
  <img src="Images/Analysis page.png" alt="IntellShield — Analysis Page" width="860"/>
  <br/><br/>
  <sub><b>Live analysis engine.</b> View plagiarism score, AI content probability, per-source URL match percentages, and the full AI method breakdown in a single panel.</sub>
</div>

---

### 📄 Analysis Report — Page 1

<div align="center">
  <img src="Images/Plagiarism and AI content analysis Report.png" alt="IntellShield — Analysis Report Page 1" width="860"/>
  <br/><br/>
  <sub><b>Downloadable PDF report — Page 1.</b> Summarises the overall plagiarism score, AI detection score, document metadata.</sub>
</div>

---

### 📄 Analysis Report — Page 2

<div align="center">
  <img src="Images/Plagiarism and AI content analysis Report2.png" alt="IntellShield — Analysis Report Page 2" width="860"/>
  <br/><br/>
  <sub><b>Downloadable PDF report — Page 2.</b>  All detected source URLs with individual match percentages.</sub>
</div>

---
## Key Features

### 🔍 Core Detection
- **Hybrid Plagiarism Detection** — combines Google Custom Search (verbatim n-gram), Common Crawl archival search, and an internal document database
- **6-Method AI Ensemble** — RoBERTa classifier, GPT-2 perplexity, burstiness analysis, stylometrics, token distribution, and AI phrase pattern matching
- **AI Model Attribution** — identifies whether content likely comes from ChatGPT, Claude, Gemini, Grok, Lovable, or generic LLMs
- **Academic Context Detection** — automatically detects academic papers and applies calibrated noise floors to prevent false positives

### 📄 Document Support
- Multi-format ingestion: **PDF, DOCX, TXT, PNG/JPG** (scanned documents via Gemini Vision OCR)
- Gemini-powered OCR with circuit breaker protection and file hash caching
- Sliding window text coverage (50-word windows, 200-word stride) for full-document analysis

### 🏗️ Platform & Workflow
- **Role-based access control** — Admin and Student dashboards with separate workflows
- **Async task queue** — Celery + Redis for background analysis jobs (up to 2-hour task limit)
- **Rate limiting** — Redis-backed moving-window rate limiter (SlowAPI) with in-memory fallback
- **Downloadable reports** — PDF analysis reports with per-source match breakdown
- **Real-time task status** — polling-based status updates for long-running analyses

### 🔐 Security
- JWT authentication (HS256) stored in HttpOnly cookies
- bcrypt password hashing
- Role-based route enforcement (`admin` / `student`)
- CORS whitelisting for known origins
- Rate limiting on login (5/min), upload (20/min), and analyse (20/min) endpoints

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 18, TypeScript, Tailwind CSS, shadcn/ui, CRACO |
| **Backend** | FastAPI (Python 3.10+), asyncpg, Pydantic |
| **AI / ML** | HuggingFace Transformers (RoBERTa, GPT-2), PyTorch, Google Gemini Vision |
| **Task Queue** | Celery, Redis |
| **Database** | PostgreSQL (asyncpg) |
| **Search** | Google Custom Search API, Common Crawl CDX API |
| **Auth** | JWT (python-jose), bcrypt (passlib) |
| **Rate Limiting** | SlowAPI (Redis-backed, in-memory fallback) |
| **Scraping** | BeautifulSoup4, Wikipedia REST API, robots.txt compliance |

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React/TS)                     │
│   LoginPage  │  StudentDashboard  │  AdminDashboard  │  Reports │
└─────────────────────────┬───────────────────────────────────────┘
                          │  HTTPS + JWT Cookie
┌─────────────────────────▼───────────────────────────────────────┐
│                   FASTAPI BACKEND                               │
│                                                                 │
│  /auth/login  │  /upload  │  /analyze  │  /status  │  /results  │
│                                                                 │
│  ┌──────────┐   ┌─────────────┐   ┌────────────────────────┐    │
│  │   Auth   │   │ Rate Limiter│   │  Role-Based Access     │    │
│  │  (JWT)   │   │  (SlowAPI)  │   │  (admin / student)     │    │
│  └──────────┘   └─────────────┘   └────────────────────────┘    │
└─────────────────────────┬───────────────────────────────────────┘
                          │  Async Task Dispatch
┌─────────────────────────▼───────────────────────────────────────┐
│                  CELERY WORKER + REDIS                          │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                  ANALYSIS PIPELINE                        │  │
│  │                                                           │  │
│  │  1. Text Extraction (Gemini OCR / PyMuPDF / python-docx)  │  │
│  │  2. Plagiarism Detection                                  │  │
│  │     ├── Google Search (verbatim n-gram, sliding window)   │  │
│  │     ├── Common Crawl CDX (archival fallback)              │  │
│  │     └── Internal DB fingerprint match                     │  │
│  │  3. AI Content Detection (6-method ensemble)              │  │
│  │     ├── M1: RoBERTa (roberta-base-openai-detector)        │  │
│  │     ├── M2: GPT-2 Perplexity                              │  │
│  │     ├── M3: Burstiness Analysis                           │  │
│  │     ├── M4: Stylometrics                                  │  │
│  │     ├── M5: Token Distribution                            │  │
│  │     └── M6: AI Phrase Pattern Matching                    │  │
│  │  4. Score Fusion + Calibration Curve                      │  │
│  │  5. Results → PostgreSQL                                  │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│                     PostgreSQL Database                         │
│   users │ documents │ analysis_results │ sources                │
└─────────────────────────────────────────────────────────────────┘
```

**Data flow (student perspective):**
1. Student logs in → JWT issued, stored in HttpOnly cookie
2. Student uploads document → file saved to disk, metadata written to DB
3. Analysis task dispatched to Celery queue via Redis
4. Worker extracts text → runs plagiarism pipeline + AI detection
5. Scores fused, calibrated, and stored in `analysis_results`
6. Frontend polls `/status/{task_id}` → renders result + allows report download

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## AI Detection Engine

IntellShield uses a **6-method weighted ensemble** to detect AI-generated content, calibrated to match AI detection output on the same reference documents.

### Method Breakdown

| Method | Weight | Description |
|--------|--------|-------------|
| **M1 — RoBERTa** | 55% | `roberta-base-openai-detector` classification (most reliable) |
| **M2 — GPT-2 Perplexity** | 10% | Low perplexity signals AI-generated fluency |
| **M3 — Burstiness** | 5% | AI text is uniformly structured; human text is bursty |
| **M4 — Stylometrics** | 5% | Detects AI-characteristic transition phrases |
| **M5 — Token Distribution** | 5% | GPT-2 token probability distribution analysis |
| **M6 — AI Phrase Patterns** | 20% | Offline regex patterns for ChatGPT, Claude, Gemini, Grok, Lovable |

### Academic Calibration

A key innovation is **academic context detection**. When a document is identified as an academic paper (via section markers like `Abstract`, `References`, `et al.`, `arxiv`, etc.), per-method noise floors are applied to prevent false positives on legitimately structured academic writing:

| Method | Noise Floor |
|--------|------------|
| Burstiness | 60% (academic papers are intentionally uniform) |
| Stylometrics | 40% (transition phrases are standard academic English) |
| Token Distribution | 50% (GPT-2 unreliable on technical text) |
| AI Patterns | 25% (generic academic phrases ≠ AI phrases) |

A post-ensemble **calibration curve** maps raw ensemble scores to final output, anchored so that a known human-written academic paper (which Turnitin scores 0%) also scores 0% in IntellShield.

### Multi-Signal Agreement

Before reporting significant AI content, at least 2 independent methods must agree:
- RoBERTa > 70% **and** GPT-2 Perplexity > 70% → bonus +4%
- AI Patterns > 50% **and** RoBERTa > 60% → bonus +3%

Maximum reportable AI score is capped at **95%** — the system never claims 100% certainty.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Plagiarism Detection Pipeline

IntellShield uses a **three-tier** plagiarism detection pipeline:

### Tier 1 — Google Custom Search (Primary)
- Splits the document into **50-word sliding windows** (200-word stride) for full-document coverage
- Runs verbatim n-gram quoted queries against the Google Custom Search API
- Computes **verbatim match percentage** using token coverage + n-gram match averaging
- Circuit breaker opens after 3 consecutive API failures, resets after 1 hour
- Redis caching of query results (24-hour TTL) to preserve the daily quota

### Tier 2 — Common Crawl CDX (Archival Fallback)
- When Google quota is exhausted or returns no results, queries the Common Crawl CDX index
- Fetches archived pages via `web.archive.org` and computes bigram overlap similarity
- Runs as a fallback — slower but free and unlimited

### Tier 3 — Internal Database Fingerprinting
- Compares incoming documents against all previously submitted documents in the institution's database
- Detects intra-institution plagiarism even when web search returns no matches

### Score Fusion

The final plagiarism score is computed by:

```
final_plagiarism_score = max(
    verbatim_web_score,      # Google Search verbatim match %
    commoncrawl_score,       # Common Crawl similarity %
    local_db_score           # Internal fingerprint match %
)
```

All matched sources (with per-URL match percentages) are stored in the database and surfaced in the report.

### Robots.txt Compliance

- Uses the general `"*"` public rule (not a named bot user agent) to respect `robots.txt` correctly
- Wikipedia URLs are routed to the official Wikipedia REST API — no scraping
- Academic domains (arXiv, CORE, Shodhganga, UGC, etc.) are whitelisted for educational use

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Getting Started

### Prerequisites

Make sure the following are installed on your machine:

- **Python** ≥ 3.10
- **Node.js** ≥ 18 and **npm**
- **PostgreSQL** ≥ 14
- **Redis** ≥ 7

### Installation

**1. Clone the repository**

```bash
git clone https://github.com/iprashanthvanam/Plagiarism_AI_detection_app.git
cd Plagiarism_AI_detection_app
```

**2. Set up the backend**

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**3. Configure environment variables**

```bash
cp .env.example .env
# Edit .env with your credentials (see Environment Variables section below)
```

**4. Set up the database**

```bash
# Run the schema
psql -U postgres -d your_db_name -f scripts/schema.sql

# Seed initial admin and student accounts
python seed.py
```

**5. Start the backend server**

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**6. Start the Celery worker** (in a new terminal)

```bash
cd backend
source venv/bin/activate
celery -A app.core.celery_client.celery_app worker --loglevel=info
```

**7. Set up and run the frontend**

```bash
cd ../frontend
npm install
npm start
```

The app will be available at `http://localhost:3000`. The API runs at `http://localhost:8000`.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Environment Variables

Create a `.env` file inside the `backend/` directory with the following keys:

```env
# ─── Database ──────────────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/intellshield

# ─── Auth ──────────────────────────────────────────────────────
SECRET_KEY=your-very-long-random-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# ─── Redis ─────────────────────────────────────────────────────
REDIS_URL=redis://localhost:6379

# ─── Google Custom Search ──────────────────────────────────────
GOOGLE_API_KEY=your-google-api-key
GOOGLE_CSE_ID=your-custom-search-engine-id

# ─── Google Gemini (Vision OCR) ────────────────────────────────
GEMINI_API_KEY=your-gemini-api-key

# ─── Storage ───────────────────────────────────────────────────
STORAGE_DIR=/path/to/uploaded/files

# ─── Rate Limits (optional — shown with defaults) ──────────────
RATE_LIMIT_LOGIN=10/minute
RATE_LIMIT_UPLOAD=20/minute
RATE_LIMIT_ANALYZE=20/minute
RATE_LIMIT_STATUS=30/minute

# ─── Analysis Config (optional) ────────────────────────────────
MIN_ANALYSIS_TEXT_LENGTH=20
SEARCH_TEXT_WORD_LIMIT=300
```

> **Getting API keys:**
> - Google Custom Search API key + CSE ID: [Google Cloud Console](https://console.cloud.google.com/) → Custom Search API
> - Gemini API key: [Google AI Studio](https://aistudio.google.com/)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Database Setup

The database schema (`backend/scripts/schema.sql`) creates the following tables:

| Table | Description |
|-------|-------------|
| `users` | Stores user accounts with hashed passwords and roles |
| `documents` | Tracks uploaded files with metadata |
| `analysis_results` | Stores plagiarism score, AI score, and calibrated breakdown |
| `sources` | Per-URL match percentages linked to each analysis result |

### Seeding

The `seed.py` script creates initial accounts for testing:

```bash
python seed.py
```

This creates:
- **Admin account:** `admin` / `admin123` (change immediately in production)
- **Student account:** `student1` / `student123`

### Database Retention

The backend runs a scheduled retention cleanup job on startup (`start_retention_scheduler()`) to automatically purge old documents and results based on configurable retention policies — keeping the database lean in production.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## API Reference

All API endpoints require a valid JWT token in the `access_token` HttpOnly cookie (set on login).

### Authentication

#### `POST /auth/login`

Rate limit: 5/minute

```
Content-Type: application/x-www-form-urlencoded

username=admin&password=admin123
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user_id": "uuid",
  "username": "admin",
  "role": "admin"
}
```

---

### Document Upload & Analysis

#### `POST /upload`

Rate limit: 20/minute | Roles: `admin`, `student`

Accepts: `multipart/form-data` with a `file` field (PDF, DOCX, TXT, PNG, JPG).

**Response:**
```json
{
  "document_id": "uuid",
  "file_name": "thesis.pdf",
  "message": "File uploaded successfully"
}
```

#### `POST /analyze/{document_id}`

Rate limit: 20/minute | Roles: `admin`, `student`

Dispatches an async Celery task for analysis.

**Response:**
```json
{
  "task_id": "celery-task-uuid",
  "status": "queued"
}
```

#### `GET /status/{task_id}`

Rate limit: 30/minute

Poll for task completion.

**Response (completed):**
```json
{
  "status": "completed",
  "result": {
    "plagiarism_score": 12.4,
    "ai_score": 0.0,
    "sources": [
      { "type": "web", "source": "https://example.com", "match_pct": 12.4 }
    ],
    "ai_breakdown": {
      "roberta": 18.2,
      "perplexity": 45.0,
      "burstiness": 0.0,
      "stylometrics": 0.0,
      "token_dist": 0.0,
      "ai_patterns": 5.2
    },
    "is_academic": true,
    "likely_ai_model": null
  }
}
```

---

### Dashboards

| Endpoint | Role | Description |
|----------|------|-------------|
| `GET /admin/dashboard` | admin | All documents across all users |
| `GET /student/dashboard` | student | Current student's documents only |

---

### Health

#### `GET /health`

Returns API status and Gemini circuit breaker state. No authentication required.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Security

IntellShield is built with a defence-in-depth approach:

| Security Layer | Implementation |
|----------------|----------------|
| **Authentication** | JWT (HS256), stored in HttpOnly cookies — prevents XSS token theft |
| **Password Storage** | bcrypt hashing via `passlib` |
| **Role Enforcement** | `require_role()` dependency injected at the route level — no role bypassing |
| **Rate Limiting** | Redis moving-window limiter (SlowAPI) with in-memory fallback if Redis is down |
| **CORS** | Strict origin whitelist (`localhost:3000`, `localhost:8000`, production URL) |
| **Input Validation** | Pydantic models validate all incoming request bodies |
| **File Handling** | Uploaded files saved with UUID filenames — no path traversal risk |
| **API Quota Protection** | Google API circuit breaker prevents quota exhaustion and runaway billing |
| **Robots.txt Compliance** | Scraper respects `robots.txt` using the general public rule; Wikipedia uses official API |

> **Production note:** Rotate `SECRET_KEY` and all seed passwords before deploying. Use environment secrets management (e.g., Render's environment group, AWS Secrets Manager) — never commit `.env` to version control.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Deployment

IntellShield is deployed on **Render** (backend + Redis) with the frontend served as a static site.

### Backend on Render (Web Service)

1. Create a new **Web Service** on Render pointing to the `backend/` directory
2. Set **Build Command:** `pip install -r requirements.txt`
3. Set **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add all environment variables from the [Environment Variables](#environment-variables) section via Render's dashboard
5. Add a **Redis** instance on Render and set `REDIS_URL` to the internal Redis URL

### Celery Worker on Render (Background Worker)

1. Create a new **Background Worker** service on Render
2. Set **Start Command:** `celery -A app.core.celery_client.celery_app worker --loglevel=info`
3. Share the same environment variables as the web service

### Frontend (Static Site)

```bash
cd frontend
npm run build
# Deploy the `build/` directory to any static host (Render, Vercel, Netlify, GitHub Pages)
```

Update `CORS` origins in `main.py` and `api.tsx` base URL to match your production domain.

### CORS Update for Production

In `backend/app/main.py`, update:
```python
origins = [
    "https://your-frontend-domain.com",
    "https://your-backend-domain.onrender.com",
]
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Project Structure

```
Plagiarism_AI_detection_app/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── admin.py          # Admin dashboard routes
│   │   │   ├── auth.py           # JWT login endpoint
│   │   │   ├── student.py        # Student dashboard routes
│   │   │   └── analysis.py       # Upload/analysis compatibility helpers
│   │   ├── core/
│   │   │   ├── celery_client.py  # Celery app initialisation
│   │   │   ├── gemini_queue.py   # Gemini concurrency semaphore
│   │   │   ├── limitter.py       # SlowAPI rate limiter setup
│   │   │   └── security.py       # JWT extraction from cookies
│   │   ├── libs/
│   │   │   ├── ai_detection.py   # 6-method AI ensemble engine
│   │   │   ├── plagiarism.py     # Score fusion logic
│   │   │   ├── google_search.py  # Google CSE + verbatim matching + circuit breaker
│   │   │   ├── commoncrawl.py    # Common Crawl CDX fallback search
│   │   │   ├── scraper.py        # robots.txt-compliant HTML scraper
│   │   │   ├── gemini_service.py # Gemini Vision OCR + circuit breaker
│   │   │   ├── extract.py        # Multi-format text extraction
│   │   │   ├── database.py       # asyncpg DB service layer
│   │   │   ├── auth.py           # bcrypt + JWT creation
│   │   │   └── models.py         # Pydantic models
│   │   ├── main.py               # FastAPI app, all routes, score engine
│   │   ├── tasks.py              # Celery analysis task definition
│   │   ├── env.py                # Environment variable loading
│   │   └── celery_config.py      # Celery configuration
│   ├── scripts/
│   │   └── schema.sql            # PostgreSQL schema
│   ├── seed.py                   # Database seeding script
│   └── requirements.txt
│
└── frontend/
    ├── src/
    │   ├── components/
    │   │   ├── LoginPage.tsx
    │   │   ├── StudentDashboard.tsx
    │   │   ├── AdminDashboard.tsx
    │   │   └── FileUploadAnalysis.tsx
    │   ├── contexts/
    │   │   └── AuthContext.tsx    # JWT-aware auth state
    │   ├── lib/
    │   │   ├── api.tsx            # Axios API client
    │   │   ├── reportGenerator.tsx# PDF report generation
    │   │   └── types.tsx          # TypeScript interfaces
    │   └── App.tsx
    ├── tailwind.config.js
    └── package.json
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Roadmap

- [x] JWT authentication with role-based access control
- [x] Multi-format document ingestion (PDF, DOCX, TXT, images)
- [x] Google Custom Search verbatim plagiarism detection
- [x] Common Crawl archival fallback search
- [x] Internal database fingerprint matching
- [x] 6-method AI detection ensemble with academic calibration
- [x] AI model attribution (ChatGPT, Claude, Gemini, Grok)
- [x] Celery async task queue with Redis
- [x] Rate limiting with circuit breaker
- [x] Downloadable PDF reports
- [x] Render cloud deployment
- [ ] Sentence-level plagiarism highlighting in the report
- [ ] Batch submission support for faculty (upload class ZIP)
- [ ] Webhook / email notification on analysis completion
- [ ] Turnitin Similarity Index comparison dashboard
- [ ] Support for Telugu and other regional language documents
- [ ] Admin analytics — institution-wide submission trends
- [ ] Docker Compose for one-command local setup

See the [open issues](https://github.com/iprashanthvanam/Plagiarism_AI_detection_app/issues) for the full list of proposed features and known issues.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Contributing

Contributions are what make open-source great. Any contributions are **greatly appreciated**.

1. Fork the project
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

Please make sure your code follows the existing structure and includes appropriate logging. For significant changes, open an issue first to discuss the approach.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## License

Distributed under the MIT License. See `LICENSE` for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Contact

<div align="center">

### Prashanth Vanam

<p>
  <a href="mailto:prashanthvanamnetha@gmail.com">
    <img src="https://img.shields.io/badge/Gmail-prashanthvanamnetha%40gmail.com-D14836?style=for-the-badge&logo=gmail&logoColor=white"/>
  </a>
  &nbsp;
  <a href="https://www.linkedin.com/in/iprashanthvanam/">
    <img src="https://img.shields.io/badge/LinkedIn-iprashanthvanam-0077B5?style=for-the-badge&logo=linkedin&logoColor=white"/>
  </a>
  &nbsp;
  <a href="https://github.com/iprashanthvanam">
    <img src="https://img.shields.io/badge/GitHub-iprashanthvanam-181717?style=for-the-badge&logo=github&logoColor=white"/>
  </a>
</p>

<p>
  <img src="https://img.shields.io/badge/📍%20Location-Hyderabad%2C%20India-f59e0b?style=for-the-badge"/>
  &nbsp;
  <img src="https://img.shields.io/badge/📞%20Mobile-%2B91%2070361%2042499-25D366?style=for-the-badge"/>
</p>

</div>

<br/>

| | |
|---|---|
| 📧 **Email** | [prashanthvanamnetha@gmail.com](mailto:prashanthvanamnetha@gmail.com) |
| 💼 **LinkedIn** | [linkedin.com/in/iprashanthvanam](https://www.linkedin.com/in/iprashanthvanam/) |
| 🐙 **GitHub** | [github.com/iprashanthvanam](https://github.com/iprashanthvanam) |
| 📍 **Location** | Hyderabad, Telangana, India |
| 📞 **Mobile** | +91 703 6142 499 |

<br/>

> 💬 Feel free to reach out for collaborations, questions, or just to say hi!

**Project Link:** [https://github.com/iprashanthvanam/Plagiarism_AI_detection_app](https://github.com/iprashanthvanam/Plagiarism_AI_detection_app)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Acknowledgments

- [HuggingFace Transformers](https://huggingface.co/transformers/) — `roberta-base-openai-detector` and `gpt2` models
- [Google Custom Search API](https://developers.google.com/custom-search) — web search for verbatim matching
- [Common Crawl](https://commoncrawl.org/) — archival web index for fallback plagiarism detection
- [Wikipedia REST API](https://www.mediawiki.org/wiki/API:Main_page) — ToS-compliant Wikipedia content access
- [Google Gemini](https://ai.google.dev/) — Vision OCR for scanned documents
- [FastAPI](https://fastapi.tiangolo.com/) — high-performance async Python API framework
- [Celery](https://docs.celeryq.dev/) — distributed task queue
- [SlowAPI](https://github.com/laurentS/slowapi) — rate limiting for FastAPI
- [shadcn/ui](https://ui.shadcn.com/) — accessible React component library
- [TKREC](https://tkrec.ac.in/) — TKR College of Engineering and Technology, the institution this system was built for

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

<div align="center">

Built with ❤️ for TKREC

⭐ Star this repo if IntellShield helped you!

</div>

