# LexNusa

An AI assistant for Indonesian law and regulations — answers come with article citations, not made-up text.

## What it does

LexNusa is a Retrieval-Augmented Generation (RAG) system that answers questions about Indonesian
legislation (laws, government regulations, presidential/ministerial regulations) and Supreme Court
rulings, sourced directly from official JDIH documents — complete with article citations and
in-force/repealed status. It targets law students, small businesses checking permit requirements,
journalists, and anyone who needs a fast answer from government regulations without digging
through PDFs one by one.

**Ingestion & data**
- Scheduled scraper (GitHub Actions cron) for JDIH Kemenkumham, peraturan.go.id, and Supreme Court rulings
- PDF parser that produces structured text per Article/Clause with type, number, and year metadata
- Automatic status tracker: in force, amended, or repealed, derived from cross-document relations

**Retrieval & reasoning**
- Structure-aware chunking — split per Article, not by arbitrary character length
- Hybrid search: keyword (BM25) + vector similarity, merged with a reranker
- Agentic router: simple questions go straight to retrieval, complex ones use multi-hop sub-queries

**Answers & trust**
- Every answer must cite its source article with a link to the original document
- Low-confidence detection — answers "not found" instead of fabricating a response
- Automatic disclaimer: this is a search aid, not a substitute for formal legal counsel

**Product & access**
- Public chat UI plus a REST API for third-party integration
- Feedback loop (relevant/not relevant) from the chat UI and `POST /api/feedback`
- Rate limiting and invite-code access (a single shared key or a per-tester key list) for a controlled soft launch

**Evaluation**
- Self-contained golden QA set (`eval/golden_qa.jsonl`) — each case ships its own reference documents
- `lexnusa-eval` runs retrieval and extractive answering against the golden set offline and reports hit rates

## Architecture

```text
JDIH scraper → Parser + chunker → Embedding → Vector DB (Qdrant)
  → Hybrid retrieval + rerank → Agent + LLM → Answer + citations
```

## Tech stack (free-tier)

| Layer | Component | Notes |
|---|---|---|
| Data | httpx + BeautifulSoup | Scraping JDIH / peraturan.go.id, free |
| Data | Supabase Storage | Stores raw PDFs & text, free tier 1GB |
| AI — embedding | sentence-transformers (multilingual-e5-base) | Runs locally/CPU, no API cost |
| AI — LLM | Groq API (Llama 3.3 / GPT-OSS) | Free tier, fast inference |
| AI — LLM fallback | Gemini API (gemini-2.0-flash) | Free tier, ~1500 req/day |
| AI — rerank | bge-reranker (local cross-encoder) | Runs on CPU |
| Vector store | Qdrant | Self-hosted Docker, or Cloud free 1GB |
| Metadata DB | Supabase / Neon Postgres | Free tier |
| Backend | FastAPI | — |
| Frontend | Next.js (or Streamlit for MVP) | — |
| Backend hosting | Railway / Render | Free tier, sleeps when idle |
| Frontend hosting | Vercel / HF Spaces | Free tier |
| Observability | Langfuse (self-hosted) | Open source, free |

## Repo layout

```text
lexnusa-rag/
├── README.md
├── docker-compose.yml
├── .github/workflows/
│   ├── scrape.yml          # cron scraping JDIH
│   └── ci.yml
├── ingestion/
│   ├── scrapers/
│   ├── parsers/
│   └── chunker.py
├── embeddings/
│   └── embed_and_index.py
├── retrieval/
│   ├── hybrid_search.py
│   └── reranker.py
├── agent/
│   ├── router.py
│   └── prompts/
├── api/
│   └── main.py              # FastAPI
├── frontend/
│   └── (Next.js app)
└── eval/
    └── golden_qa.jsonl      # manual evaluation dataset
```

## Replicating this project

Requirements: Python 3.9+. All commands below use free-tier services; `GROQ_API_KEY` is optional
since extractive mode runs fully offline.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Scrape ~100 sample UU/PP documents from JDIH (checks robots.txt, 2s minimum delay).
lexnusa-scrape --limit 100 --delay 2

# Extract PDFs, split per Article, and index into local Qdrant.
lexnusa-index

# Hybrid retrieval with no external API calls.
lexnusa-ask --no-llm "What are the witness protection provisions?"
```

For generative answers, set `GROQ_API_KEY` and run `lexnusa-ask` without `--no-llm`. The answer
always lists its sources (article and official PDF URL) plus the disclaimer. If the index is
empty, the system refuses to invent an answer and reports that nothing was found.

Run the test suite without touching any government site:

```bash
pytest -q
```

A local hash embedding is used as a reproducible, download-free baseline; swapping in
`multilingual-e5-base` is a drop-in replacement for a later retrieval-quality pass.

### Retrieval backend (Qdrant)

Qdrant can run embedded in a local folder (default), via Docker, or on Qdrant Cloud.

```bash
# Embedded: no separate server needed.
lexnusa-index
lexnusa-ask --backend qdrant --no-llm "What are the witness protection provisions?"

# Local BGE reranker (model downloads once from Hugging Face).
pip install -e ".[rerank]"
lexnusa-ask --backend qdrant --rerank --no-llm "What are the witness protection provisions?"

# Local Qdrant server; point the CLI at it via an environment variable once it's up.
docker compose up -d qdrant
export QDRANT_URL=http://localhost:6333
lexnusa-index --no-parse
```

For Qdrant Cloud, set `QDRANT_URL` and `QDRANT_API_KEY`. Retrieval merges semantic candidates
from Qdrant with BM25 keyword candidates using Reciprocal Rank Fusion (RRF), then runs
`BAAI/bge-reranker-v2-m3` when `--rerank` is passed. The `lexnusa-qdrant-index` alias remains
available. For the Chroma-based compatibility path, use `lexnusa-chroma-index` then
`lexnusa-ask --backend chroma`.

### Legal status & the agent router

The scraper reads status and `amends`/`repeals` relations from official detail pages. During
indexing, those relations propagate to the target document so an older regulation gets tagged
`amended` or `repealed`. When a source provides no status, the answer labels it `unverified`
rather than guessing.

```bash
# Refetch status metadata, then rebuild the Qdrant index.
lexnusa-scrape --limit 100 --delay 2
lexnusa-index

# Inspect the router's decision and the sub-queries it ran.
lexnusa-ask --show-plan --no-llm \
  "Compare witness protection and victim protection across the relevant laws"

# Status questions widen retrieval to amendment/repeal relations.
lexnusa-ask --show-plan --no-llm "Is Law No. 1 of 2020 still in force?"
```

The router runs locally with no LLM call: simple questions use a single retrieval pass, status
questions add a relation query, and comparison/complex questions fan out into several
deduplicated sub-queries. Both the generative and extractive answer paths show each source's
status, article, official PDF URL, and the disclaimer.

### API & chat UI

Run the API and chat UI from a single process:

```bash
source .venv/bin/activate
lexnusa-api
```

Open `http://localhost:8000`. OpenAPI docs are at `http://localhost:8000/docs`, a health check
at `/health`, and the chat endpoint at `POST /api/chat`:

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"Is Law No. 1 of 2020 still in force?","use_llm":false}'
```

Runtime configuration:

| Variable | Purpose | Default |
|---|---|---|
| `LEXNUSA_INDEX_DIR` | Embedded Qdrant location | `data/qdrant` |
| `QDRANT_URL` | Qdrant server/Cloud endpoint | empty |
| `QDRANT_API_KEY` | Qdrant Cloud credential | empty |
| `GROQ_API_KEY` | Optional generative answers | empty |
| `LEXNUSA_API_KEY` | Require a single shared `X-API-Key` | empty/public |
| `LEXNUSA_API_KEYS` | Comma-separated per-tester invite codes | empty |
| `LEXNUSA_RATE_LIMIT` | Max requests per minute per client | `30` |
| `LEXNUSA_FEEDBACK_FILE` | Where feedback JSON lines are appended | `data/feedback.jsonl` |

The repo includes a `Dockerfile` and `render.yaml`. For a Render deployment, connect the repo as
a Blueprint, set `QDRANT_URL`/`QDRANT_API_KEY`, and add `GROQ_API_KEY` for generative mode. The
UI and API are deliberately served from the same origin so no CORS configuration or separate
frontend deployment is needed.

### Evaluation & feedback

The golden QA set lives at `eval/golden_qa.jsonl`. Each case is self-contained — its reference
documents travel with it in the same JSON line — so evaluation stays reproducible and offline
even with no real scraped data on the machine running it.

```bash
lexnusa-eval --golden eval/golden_qa.jsonl --output reports/eval.json
```

Each case is scored two ways: whether the expected document/article shows up in retrieval
(`retrieval_hit`), and whether the final answer contains the expected keywords (`keyword_hit`).
The command exits non-zero if any case fails, so it can act as a CI regression gate before
widening access.

User feedback (relevant/not relevant) is sent automatically via the 👍/👎 buttons in the chat UI,
or directly to `POST /api/feedback`:

```json
{"question":"...","answer":"...","relevant":true,"comment":"optional"}
```

Each feedback entry is appended as a JSON line to `LEXNUSA_FEEDBACK_FILE` with a UTC timestamp
and the sender's API key/IP, for manual review when assessing retrieval quality after a soft
launch.

For a controlled soft launch, replace a single `LEXNUSA_API_KEY` with `LEXNUSA_API_KEYS` (a
comma-separated list) — each tester gets their own invite code, so access can be revoked
per-person without rotating a key everyone shares:

```bash
export LEXNUSA_API_KEYS="tester-a,tester-b,tester-c"
```

## Notes

**Not legal advice.** Every answer must keep showing its original sources and the disclaimer
that this is a search aid, not a substitute for formal legal counsel. Before any large-scale
scraping, check the target government site's `robots.txt` and terms of use, and keep request
rates low so public servers aren't overloaded.
