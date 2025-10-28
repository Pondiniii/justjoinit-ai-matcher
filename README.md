# 🤖 AI Job Finder for JustJoin.IT

> Automated job scraping, LLM-powered analysis, and intelligent matching for JustJoin.IT offers

An intelligent job search automation system that scrapes job offers from JustJoin.IT, analyzes them using Large Language Models, and matches them against your profile to help you find the perfect job faster.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: GPL-3.0](https://img.shields.io/badge/License-GPL%203.0-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

---

## 📋 Table of Contents

- [Features](#-features)
- [How It Works](#-how-it-works)
- [Architecture](#-architecture)
- [Screenshots](#-screenshots)
- [Prerequisites](#-prerequisites)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [Database Schema](#-database-schema)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)
- [License](#-license)

---

## ✨ Features

- 🕷️ **Automated Scraping**: Fetches job offers from JustJoin.IT with customizable filters (remote, B2B, experience level, salary)
- 🤖 **LLM Analysis**: 4-stage AI pipeline optimized for smaller models (7B-20B parameters)
- 🎯 **Smart Matching**: Analyzes job fit based on your profile, skills, and preferences
- 📊 **Risk Scoring**: Evaluates offers on multiple dimensions (company culture, stability, red flags)
- 💾 **PostgreSQL Storage**: Structured data storage with normalized tags and efficient querying
- 📈 **Metabase Dashboard**: Beautiful UI for exploring results and generating reports
- 🔄 **Idempotent**: Safe to re-run - automatically handles duplicates
- ⚡ **Concurrent Processing**: Multi-threaded pipeline for faster analysis

---

## 🔍 How It Works

### 3-Phase Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│  Phase 1: Discovery                                              │
│  ├─ Scrape JustJoin.IT HTML pages                                │
│  ├─ Extract job offer URLs                                       │
│  └─ Store in PostgreSQL (status: 'discovered')                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  Phase 2: Fetching & Parsing                                     │
│  ├─ Fetch each job offer page                                    │
│  ├─ Parse HTML → structured data                                 │
│  └─ Extract: title, company, salary, tech stack, requirements    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  Phase 3: LLM Analysis (4-Stage Scoring)                         │
│  ├─ Stage 1: Tag extraction + summary                            │
│  ├─ Stage 2: Risk scores (red flags, culture, stability)         │
│  ├─ Stage 3: Fit analysis (match against your profile)           │
│  ├─ Stage 4: Final decision (APPLY / WATCH / IGNORE)             │
│  └─ Save results (status: 'scored')                              │
└─────────────────────────────────────────────────────────────────┘
```

### 4-Stage LLM Scoring

Why 4 separate stages instead of one big prompt?

- ✅ **More reliable**: Smaller prompts = better JSON parsing with smaller models
- ✅ **Easier debugging**: Know exactly which stage failed
- ✅ **Better context**: Each stage focuses on one task
- ✅ **Optimized for 7B-20B models**: Works great even without GPT-4

---

## 🏗️ Architecture

```
├── scripts/
│   ├── fetch_offers.sh      # HTML scraper (multi-page pagination)
│   └── parse_pages.py       # HTML → JSON converter
├── db/
│   └── manager.py           # PostgreSQL operations
├── parsing/
│   └── offer_parser.py      # Job offer HTML parser
├── llm/
│   ├── client.py            # LLM HTTP client (OpenAI-compatible)
│   └── unified_scorer.py    # 4-stage scoring pipeline
├── pipeline/
│   └── processor.py         # Main orchestration logic
├── main.py                  # CLI entry point
├── config.py                # Configuration (LLM API settings)
├── schema.sql               # PostgreSQL schema
└── docker-compose.yml       # PostgreSQL + Metabase services
```

---

## 📊 Example Results

### Top APPLY Matches (Real Data)

| Company | Title | Salary | Fit Score | Reasoning (excerpt) |
|---------|-------|--------|-----------|---------------------|
| **Humanit** | AI Agent Engineer (Integrations) | 29k-49k PLN | **98** | *Idealnie pasuje: rola skupiona na budowaniu AI agents z LLM, architektura i autonomia w fast-growing SaaS startupie, Python/LLMs, 100% remote B2B, wysoka autonomia bez micromanagementu...* |
| **Callstack** | Senior AI System Engineer | 29k-42k PLN | **95** | *Fokus na projektowaniu end-to-end LLM i multi-agent architectures, Python core, cloud infra (AWS/GCP), security i automatyzacja. Remote B2B, autonomia w R&D i open-source...* |
| **best HR** | GenAI Tooling Engineer | 120-190 PLN/h | **95** | *Fokus na GenAI tooling, integracja LLM, RAG, automatyzacja workflow z Python, K8s i CI/CD. 100% remote B2B, autonomia w prototypowaniu...* |

### WATCH Offers

| Company | Title | Salary | Fit Score | Reasoning (excerpt) |
|---------|-------|--------|-----------|---------------------|
| **hyperexponential** | AI Engineer | 29k-37k PLN | **85** | *Pasuje dzięki fokusowi na AI enablement, automatyzację i LLM w developer workflows...* |
| **ITDS** | Senior AI Agentic Engineer | 26k-29k PLN | **85** | *Idealnie pasuje do pasji w LLM agents, automatyzacji i projektowaniu systemów - Python, LangChain, cloud...* |

### IGNORE Examples

| Title | Fit Score | Why Rejected |
|-------|-----------|--------------|
| Freelance Senior Full Stack Developer | **20** | *Onsite w Warszawie (deal breaker), stack JS/TS/Node.js to blacklista* |
| Golang Developer (Azure) | **30** | *Stack Golang nie jest w core skills, brak fokus na AI/automatyzacji* |

### Analysis Statistics

```
┌──────────┬───────┬─────────────┬─────────┬─────────┐
│ Decision │ Count │ Avg Fit     │ Min Fit │ Max Fit │
├──────────┼───────┼─────────────┼─────────┼─────────┤
│ IGNORE   │ 1,908 │ 20          │ 0       │ 85      │
│ WATCH    │   168 │ 64          │ 40      │ 85      │
│ APPLY    │    71 │ 84          │ 65      │ 98      │
└──────────┴───────┴─────────────┴─────────┴─────────┘

Total Analyzed: 2,147 offers
Acceptance Rate: 3.3% (APPLY) | 7.8% (WATCH) | 89% (IGNORE)
```

### Processing Status

```
┌────────────┬───────┐
│ Status     │ Count │
├────────────┼───────┤
│ analyzed   │ 2,147 │
│ discovered │   116 │
│ fetched    │     1 │
└────────────┴───────┘
```

---

## 📦 Prerequisites

- **Python 3.8+**
- **Docker & Docker Compose** (for PostgreSQL and Metabase)
- **LLM API Access**: One of:
  - [xAI Grok API](https://console.x.ai/) (recommended, $5/month for Grok 4 Fast)
  - [OpenAI API](https://platform.openai.com/)
  - Local LLM server ([LM Studio](https://lmstudio.ai/), [llama.cpp](https://github.com/ggerganov/llama.cpp), [vLLM](https://github.com/vllm-project/vllm))

---

## 🚀 Installation

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/auto-justjoinit-job-finder.git
cd auto-justjoinit-job-finder
```

### 2. Start PostgreSQL and Metabase

```bash
docker-compose up -d
```

Wait ~30 seconds for the database health check to pass:

```bash
docker ps | grep justjoinit_db  # Should show "healthy"
```

### 3. Set up Python environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
nano .env  # Edit with your settings
```

**Required:** Set your `LLM_API_KEY` in the `.env` file:

```env
LLM_API_KEY=your-actual-api-key-here
```

### 5. Create your profile

Copy the example file and customize it:

```bash
cp system_prompt_example.md system_prompt.md

# Edit with your preferences (skills, salary, requirements)
nano system_prompt.md
```

**Important:** `system_prompt.md` is in `.gitignore` and won't be committed to prevent exposing personal data.

---

## ⚙️ Configuration

### Environment Variables (.env)

```env
# LLM API Configuration
LLM_BASE_URL=https://api.x.ai/v1              # API endpoint
LLM_MODEL=grok-4-fast-non-reasoning           # Model name
LLM_TIMEOUT=180                                # Request timeout (seconds)
LLM_API_KEY=your-api-key-here                 # Your API key

# Database (docker-compose)
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=justjoinit
```

### Job Search Filters (scripts/fetch_offers.sh)

Edit the `BASE_URL` to customize your search:

```bash
BASE_URL="https://justjoin.it/job-offers/remote?employment-type=b2b&experience-level=mid,senior&with-salary=yes&orderBy=DESC&sortBy=published"
```

**Available filters:**
- `employment-type`: `b2b`, `permanent`, `contract`
- `experience-level`: `junior`, `mid`, `senior`
- `with-salary=yes`: Only offers with salary info
- `orderBy=DESC&sortBy=published`: Newest first

### System Prompt (system_prompt.md)

This file contains your complete candidate profile and defines:
- Your skills and experience
- Tech stack preferences (must-have, avoid)
- Work culture requirements (remote, salary, autonomy)
- Scoring criteria for the AI
- Salary expectations
- Company preferences

See `system_prompt_example.md` for the template.

**Note:** All candidate profile information is in this single file - there's no separate JSON config needed.

---

## 🎯 Usage

### Basic Workflow

```bash
# 1. Scrape job offers
./scripts/fetch_offers.sh
```

**Example output:**
```
🔍 Fetching ALL offers from JustJoin.IT...

📥 Downloading first page...
  → 6252 offers across 63 pages

📥 Downloading page 2/63...
📥 Downloading page 3/63...
...
📥 Downloading page 63/63...

✓ Downloaded 63 HTML pages

📝 Parsing HTML → JSON...
✓ Parsed 2210 unique offers
✓ Saved to data/offers.json

🎉 Done! Run: python main.py
```

```bash
# 2. Process all discovered offers (1 worker)
python main.py
```

**Example output:**
```
============================================================
🤖 JustJoinIT AI Analyzer - 3-Phase Pipeline
============================================================
⚙️  Workers: 1
✓ LLM server reachable

🔍 Phase 1: Discovery
✓ Loaded 2210 links from offers.json

📥🤖 Phase 2+3: Fetch → Analyze (sequential, limit=all)
[1/2210] Fetching https://justjoin.it/job-offer/...
[1/2210] ✓ Fetched (desc: 2385 chars)
[1/2210] Analyzing...
[1/2210] ✓ IGNORE (fit=10)
[2/2210] ✓ APPLY (fit=98)
...

✓ Processed: 2210/2210

📈 Database Statistics
  Total Links    : 2264
  Discovered     : 0
  Fetched        : 0
  Analyzed       : 2264
  Apply          : 71
  Watch          : 168
  Ignore         : 2025
```

```bash
# 3. View results in Metabase or pgweb
open http://localhost:8081  # pgweb UI
```

### Advanced Usage

```bash
# Process only 10 offers (for testing)
python main.py 10

# Process 100 offers with 4 parallel workers
python main.py 100 --workers 4

# Process all offers with 10 parallel workers (fastest)
python main.py --workers 10

# Custom offers file path
python main.py 50 custom_offers.json
```

### Database Management

```bash
# Wipe database (interactive tool with options)
python wipe_db.py

# Quick stats via CLI
docker exec justjoinit_db psql -U postgres -d justjoinit -c "SELECT * FROM v_stats;"

# View top matches
docker exec justjoinit_db psql -U postgres -d justjoinit -c \
  "SELECT title, company, fit_score, decision FROM job_offers WHERE decision='APPLY' ORDER BY fit_score DESC LIMIT 10;"
```

---

## 📊 Database Schema

### Core Tables

#### `job_links`
- Stores discovered job URLs
- Status: `discovered` → `parsed` → `scored`
- Unique constraint on `link`

#### `job_details`
- Parsed job information (title, company, salary, tech stack)
- JSONB fields for flexible data storage
- References `job_links` (cascade delete)

#### `job_analysis`
- LLM analysis results (scores, reasoning, decision)
- Risk scores: januszex, culture, stability, etc.
- Fit analysis: fit_score, matched/missing/avoided tags
- Final decision: `APPLY` / `WATCH` / `IGNORE`

#### `tech_tags`
- Normalized tag storage (prevents duplicates)
- Usage counter for popularity tracking
- Used in LLM prompts for tag reuse

### Views

#### `v_job_offers`
- Unified view joining all tables
- Main query interface for Metabase

#### `v_stats`
- Real-time statistics (total, discovered, parsed, scored)

#### `v_top_matches`
- Pre-filtered view: `decision='APPLY'` and `fit_score > 70`

---

## 📈 Viewing Results

### Option 1: pgweb (Simple, Fast)

Open http://localhost:8081

**Pre-configured:** No setup needed, browse tables directly!

**Useful Queries:**
- Browse `job_analysis` table to see all scored offers
- Join with `job_details` for full information
- Filter by `decision = 'APPLY'` for top matches

### Useful Queries

**Top Matches:**
```sql
SELECT
  d.title,
  d.company,
  d.salary_min,
  d.salary_max,
  a.fit_score,
  a.decision,
  l.link
FROM job_links l
JOIN job_details d ON l.id = d.link_id
JOIN job_analysis a ON l.id = a.link_id
WHERE a.decision = 'APPLY'
ORDER BY a.fit_score DESC
LIMIT 20;
```

**Salary Analysis:**
```sql
SELECT
  a.decision,
  ROUND(AVG(d.salary_min)) as avg_min,
  ROUND(AVG(d.salary_max)) as avg_max,
  COUNT(*) as count
FROM job_analysis a
JOIN job_details d ON a.link_id = d.link_id
WHERE d.salary_min IS NOT NULL
GROUP BY a.decision;
```

**Filter by Technology:**
```sql
SELECT
  d.title,
  d.company,
  a.fit_score,
  a.decision
FROM job_details d
JOIN job_analysis a ON d.link_id = a.link_id
WHERE d.tech_stack::text ILIKE '%kubernetes%'
  AND a.decision = 'APPLY'
ORDER BY a.fit_score DESC;
```

---

## 🛠️ Troubleshooting

### LLM API Issues

**Error:** `LLM_API_KEY environment variable is required!`

**Solution:** Create `.env` file from `.env.example` and set your API key:
```bash
cp .env.example .env
nano .env  # Add: LLM_API_KEY=your-key-here
```

**Error:** `LLM server not reachable`

**Solution:**
- Check `LLM_BASE_URL` in `.env`
- Test API: `curl $LLM_BASE_URL/models -H "Authorization: Bearer $LLM_API_KEY"`
- Increase `LLM_TIMEOUT` if requests are timing out

### Database Issues

**Error:** `Connection refused` when connecting to PostgreSQL

**Solution:**
```bash
# Check if database is running
docker ps | grep justjoinit_db

# Check logs
docker logs justjoinit_db

# Restart services
docker-compose restart
```

**Reset database completely:**
```bash
docker-compose down -v  # Remove volumes
docker-compose up -d    # Restart
```

### Scraping Issues

**No offers found after running `fetch_offers.sh`**

**Check:**
1. Is `data/offers.json` created?
2. Run `cat data/offers.json | head` to see contents
3. Check for HTML changes on JustJoin.IT (regex patterns may need updating)

**Rate limiting / 429 errors:**

Edit `scripts/fetch_offers.sh` and increase sleep time:
```bash
sleep 2.0  # Increase from 0.5 to 2.0 seconds
```

---

## 🏃 Performance Tips

1. **Use filtered URLs**: Pre-filter on JustJoin.IT reduces processing time
   - Example: 6,252 total offers → 2,210 with filters (65% reduction)
   - Edit `BASE_URL` in `scripts/fetch_offers.sh`

2. **Parallel workers**: Use `--workers 10` for 10x speedup
   - Sequential: ~5-10s per offer
   - Parallel (10 workers): process 10 offers simultaneously
   - Be mindful of LLM API rate limits

3. **LLM choice**:
   - **Fast:** Grok 4 Fast (~2-3s/offer), $5/month - recommended!
   - **Accurate:** GPT-4 (~5-10s/offer), expensive
   - **Free:** Local LLM via LM Studio (7B-20B models), slower

4. **Smaller batches**: Test with `python main.py 10` before processing all offers

5. **Real stats from production:**
   - 2,147 offers analyzed
   - **71 APPLY** (3.3%) - highly targeted results!
   - Average processing: ~5-8s per offer (Grok 4 Fast)

---

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📝 License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

---

## ⚠️ Disclaimer

This tool is for personal use only. Please respect JustJoin.IT's terms of service and rate limits. The built-in delays (2s between requests) help prevent server overload.

---

**Happy job hunting! 🚀**

If you find this useful, please ⭐ star the repository!
