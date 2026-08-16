# LexNusa

Asisten AI untuk regulasi dan putusan hukum Indonesia — dijawab dengan kutipan pasal, bukan karangan.

> Status: **Blueprint** — belum ada kode yang dibangun. Lihat [`lexnusa-rag-blueprint.pdf`](./lexnusa-rag-blueprint.pdf) untuk versi visual lengkap, atau bagian di bawah untuk ringkasan teks.

## Ringkasan

LexNusa adalah sistem RAG (Retrieval-Augmented Generation) yang menjawab pertanyaan seputar
peraturan perundang-undangan Indonesia (UU, PP, Perpres, Permen) dan putusan Mahkamah Agung,
langsung dari dokumen resmi JDIH — lengkap dengan kutipan pasal dan status berlaku/dicabut.

Target pengguna: mahasiswa hukum, UMKM yang cek perizinan, jurnalis, dan siapa pun yang butuh
jawaban cepat dari regulasi pemerintah tanpa menggali PDF satu per satu.

## Fitur utama

**Ingestion & Data**
- Scraper terjadwal (GitHub Actions cron) untuk JDIH Kemenkumham, peraturan.go.id, dan putusan MA
- Parser PDF → teks terstruktur per Pasal/Ayat dengan metadata jenis, nomor, dan tahun
- Status tracker otomatis: berlaku, diubah, atau dicabut, dari relasi antar dokumen

**Retrieval & Reasoning**
- Chunking sadar-struktur — dipotong per Pasal, bukan sembarang panjang karakter
- Hybrid search: keyword (BM25) + vector similarity, digabung reranker
- Agent router: pertanyaan sederhana langsung retrieve, pertanyaan kompleks pakai multi-hop

**Jawaban & Kepercayaan**
- Setiap jawaban wajib menyertakan kutipan pasal dan tautan ke dokumen asli
- Deteksi low-confidence — jawab "tidak ditemukan" alih-alih mengarang
- Disclaimer otomatis: bukan pengganti konsultasi hukum resmi

**Produk & Akses**
- Chat UI publik plus REST API untuk integrasi pihak ketiga
- Feedback loop (relevan/tidak) untuk evaluasi kualitas retrieval
- Rate limiting dan API key untuk kontrol biaya

## Arsitektur

```
Scraper JDIH → Parser + Chunker → Embedding → Vector DB (Qdrant)
  → Hybrid Retrieval + Rerank → Agent + LLM → Jawaban + Sitasi
```

## Tech stack (free-tier)

| Layer | Komponen | Catatan |
|---|---|---|
| Data | httpx + BeautifulSoup | Scraping JDIH / peraturan.go.id, gratis |
| Data | Supabase Storage | Simpan PDF & teks mentah, free tier 1GB |
| AI — Embedding | sentence-transformers (multilingual-e5-base) | Jalan lokal/CPU, tanpa biaya API |
| AI — LLM | Groq API (Llama 3.3 / GPT-OSS) | Free tier, inference cepat |
| AI — LLM cadangan | Gemini API (gemini-2.0-flash) | Free tier ~1500 req/hari |
| AI — Rerank | bge-reranker (cross-encoder lokal) | Jalan CPU |
| Vector store | Qdrant | Self-host Docker, atau Cloud free 1GB |
| Metadata DB | Supabase / Neon Postgres | Free tier |
| Backend | FastAPI | — |
| Frontend | Next.js (atau Streamlit untuk MVP) | — |
| Hosting backend | Railway / Render | Free tier, sleep saat idle |
| Hosting frontend | Vercel / HF Spaces | Free tier |
| Observability | Langfuse (self-host) | Open source, gratis |

## Struktur repo (target)

```
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
    └── golden_qa.jsonl      # dataset evaluasi manual
```

## Roadmap

| # | Milestone | Deskripsi |
|---|---|---|
| M0 | Scraper minimal | Ambil ~100 dokumen UU/PP sample dari JDIH, simpan mentah |
| M1 | Parsing & chunking | Pecah per Pasal, index ke Chroma lokal untuk eksperimen cepat |
| M2 | RAG pipeline manual | End-to-end lewat CLI: retrieve → prompt → jawaban bersitasi |
| M3 | Retrieval production-grade | Migrasi ke Qdrant, tambah hybrid search dan reranker |
| M4 | Agent & status-aware answer | Router agentic, deteksi peraturan yang sudah dicabut/diubah |
| M5 | API, UI, deploy | FastAPI + frontend chat, live di hosting gratis |
| M6 | Eval & soft launch | Golden QA set, feedback loop, buka akses terbatas ke publik |

## Catatan

**Bukan nasihat hukum.** Setiap jawaban harus tetap menampilkan sumber asli dan disclaimer
bahwa ini alat bantu pencarian, bukan pengganti konsultasi hukum resmi. Sebelum scraping
besar-besaran, cek `robots.txt` dan ketentuan penggunaan situs pemerintah terkait, dan batasi
rate request supaya tidak membebani server publik.
