# 📄 Living API Docs

> **An Event-Driven, AI-Augmented System for Auto-Updating Developer-Friendly API Documentation**

[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.38-red?logo=streamlit)](https://streamlit.io)
[![Groq](https://img.shields.io/badge/LLM-llama--3.3--70b-orange)](https://console.groq.com)
[![FAISS](https://img.shields.io/badge/RAG-FAISS-green)](https://faiss.ai)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## 🧠 The Problem

API documentation is **always stale**. Developers write it once, the API evolves, and docs never catch up. The result: broken examples, undocumented endpoints, and hours wasted debugging because developers trusted wrong docs.

## ✨ The Solution

**Living API Docs** watches your GitHub repository for changes. The moment you push updated API code, the system automatically:

1. 🔍 **Detects** which API endpoints changed
2. 🤖 **Generates** comprehensive, developer-friendly documentation using LLaMA 3.3 70B via Groq
3. ✅ **Presents** a draft for your review — approve, edit, or reject
4. 📧 **Notifies** you via email with a magic link to review the updated docs
5. 🌐 **Publishes** approved docs to GitHub Pages or exports as Markdown / Swagger YAML

---

## 🎬 Demo Flow

```
You push code → System detects API change → LLM generates docs
→ Email arrives with magic link → Click → Review & approve
→ Export to GitHub Pages → Live docs URL ready
```
## Check the Live Demo -- https://living-api-docs-generator.streamlit.app/
---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Living API Docs                       │
├─────────────┬──────────────┬────────────┬───────────────┤
│   Parser    │    RAG       │    LLM     │   Publisher   │
│             │              │            │               │
│ FastAPI     │ FAISS        │ Groq       │ Markdown      │
│ Flask       │ all-MiniLM   │ LLaMA 3.3  │ Swagger YAML  │
│ Django      │ Embeddings   │ 70B        │ GitHub Pages  │
│ Express.js  │              │            │ Email (SG)    │
│ Spring Boot │              │            │               │
└─────────────┴──────────────┴────────────┴───────────────┘
         ↑                                        ↑
   GitHub Polling                          Streamlit UI
   + Webhook Service                      (3-page app)
   (Railway — always on)
```

### Key Innovation — Code-Doc Consistency Checker
Every AI-generated doc is cross-referenced against actual source code. Claims about OAuth, JWT, rate limiting, pagination, or caching are automatically verified. If a claim has no matching code evidence, it's flagged before publishing — preventing hallucinated documentation.

---

## 🚀 Features

| Feature | Description |
|---------|-------------|
| **Multi-framework support** | FastAPI, Flask, Django REST, Express.js, Spring Boot |
| **Event-driven** | Polls GitHub every 30s + optional always-on webhook via Railway |
| **RAG-powered** | Retrieves old docs via FAISS before updating — maintains consistency |
| **Draft → Review → Approve** | Full human-in-the-loop workflow |
| **Consistency checker** | Flags AI claims not supported by actual code |
| **Version history** | Every approval creates a snapshot with diff view |
| **Email notifications** | SendGrid alerts with magic login links |
| **Multiple export formats** | Markdown, OpenAPI/Swagger YAML, GitHub Pages |
| **Email auth** | No passwords — magic link login |

---

## 📁 Project Structure

```
living-api-docs/
├── streamlit/               # UI Dashboard
│   ├── app.py               # Entry point
│   └── pages/
│       ├── 0_login.py       # Email auth
│       ├── 1_repo_scan.py   # Add & monitor repos
│       ├── 2_review_draft.py # Review/approve docs
│       └── 3_history.py     # Version history + diff
│
├── parser/                  # Framework-specific parsers
│   ├── detect_framework.py
│   ├── fastapi_parser.py
│   ├── flask_parser.py
│   ├── django_parser.py
│   ├── express_parser.py
│   └── springboot_parser.py
│
├── rag/                     # RAG pipeline
│   ├── embedder.py          # all-MiniLM-L6-v2 embeddings
│   ├── vector_store.py      # FAISS store
│   └── retriever.py         # Old doc retrieval
│
├── llm/                     # LLM layer
│   ├── generator.py         # Groq doc generation
│   └── consistency_checker.py # Code-doc verification
│
├── publisher/               # Output formats
│   ├── markdown_exporter.py
│   ├── swagger_exporter.py
│   ├── github_pages.py
│   └── email_notifier.py
│
├── poller/
│   └── poller.py            # Background GitHub polling daemon
│
├── storage/
│   └── db.py                # SQLite — all persistent state
│
├── data/                    # Runtime data (gitignored)
│   ├── cloned_repos/
│   ├── faiss_index/
│   └── generated_docs/
│
├── .env.example             # Environment template
├── requirements.txt
└── README.md
```

---

## ⚙️ Setup & Installation

### Prerequisites
- Python 3.10+
- Git installed

### 1. Clone the repo
```bash
git clone https://github.com/anushree196/living-api-docs.git
cd living-api-docs
```

### 2. Create virtual environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install --upgrade pip
pip install protobuf==3.20.3
pip install -r requirements.txt
```

### 4. Configure environment
```bash
cp .env.example .env
# Edit .env and fill in your API keys
```

You need:
- **Groq API key** → [console.groq.com](https://console.groq.com) (free)
- **GitHub Personal Access Token** → GitHub Settings → Developer Settings → Tokens → `repo` scope
- **SendGrid API key** → [sendgrid.com](https://sendgrid.com) (optional, for email alerts)

### 5. Run
```bash
cd streamlit
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) 🎉

---

## 🧪 Testing the System

### Quick test with a sample FastAPI repo:
1. Go to **Repo Scanner** page
2. Paste: `https://github.com/BaseMax/SimpleFastPyAPI`
3. Click **Scan Now**
4. Watch terminal: `[Generator] SUCCESS: GET /users/ (2182 chars)`
5. Go to **Review Drafts** → see AI-generated docs for all 5 endpoints
6. Approve → Export Markdown or publish to GitHub Pages

### Test the living part:
1. Fork any of the test repos to your GitHub
2. Make a change to an API endpoint
3. Push the change
4. Watch the system auto-detect and regenerate docs within 30 seconds

---

## 📡 Webhook Service (Optional — for always-on detection)

For detection even when Streamlit is sleeping, deploy the companion webhook service to Railway:

See [`webhook-service/README.md`](webhook-service/README.md) for full setup guide.

```
GitHub push → Railway webhook → Generate docs → SendGrid email → Magic link login
```

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| UI | Streamlit 1.38 |
| LLM | LLaMA 3.3 70B via Groq API |
| Embeddings | all-MiniLM-L6-v2 (sentence-transformers) |
| Vector Store | FAISS (Facebook AI Similarity Search) |
| Database | SQLite |
| Email | SendGrid |
| Code Parsing | Python AST + Regex |
| Version Control | GitHub REST API |
| Deployment | Streamlit Community Cloud + Railway |

---

## 🎓 Built as a part of semester project 

This project builds on concepts from the previous **AI Knowledge Graph Builder** project:
- FAISS RAG pipeline (adapted from KG retrieval)
- LangChain patterns (replaced with direct Groq SDK for reliability)
- Streamlit dashboard patterns

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

*Built with ❤️ by Anushree | Powered by Groq + FAISS + Streamlit*
