# LexNusa

Asisten AI untuk regulasi dan putusan hukum Indonesia — dijawab dengan kutipan pasal, bukan karangan.

> Status: **M5 — API, UI & deploy-ready**. FastAPI, chat UI responsif, router single/multi-hop,
> status hukum, Qdrant hybrid retrieval, API key, dan rate limiting sudah tersedia.

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

## Menjalankan M0-M3

Prasyarat: Python 3.9 atau lebih baru. Semua perintah berikut menggunakan layanan gratis;
`GROQ_API_KEY` bersifat opsional karena mode ekstraktif dapat berjalan sepenuhnya lokal.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# M0: cek robots.txt, beri jeda minimum 2 detik, lalu simpan PDF + metadata.
lexnusa-scrape --limit 100 --delay 2

# M1-M3: ekstrak PDF, pecah per Pasal, dan indeks ke Qdrant lokal.
lexnusa-index

# M2-M3: hybrid retrieval tanpa API eksternal.
lexnusa-ask --no-llm "Apa ketentuan mengenai perlindungan saksi?"
```

Untuk jawaban generatif, isi `GROQ_API_KEY` lalu jalankan `lexnusa-ask` tanpa `--no-llm`.
Jawaban tetap menampilkan daftar sumber (pasal dan URL PDF resmi) serta disclaimer. Jika indeks
kosong, sistem menolak mengarang dan menyatakan informasi tidak ditemukan.

Jalankan pengujian tanpa mengakses situs pemerintah:

```bash
pytest -q
```

Catatan teknis: embedding hash lokal tetap dipakai sebagai baseline reproducible tanpa unduhan.
Penggantian ke `multilingual-e5-base` dijadwalkan pada iterasi evaluasi retrieval berikutnya.

## Menjalankan M3

Qdrant dapat berjalan embedded di folder lokal (default), melalui Docker, atau Qdrant Cloud.

```bash
# Embedded: tidak membutuhkan server terpisah.
lexnusa-index
lexnusa-ask --backend qdrant --no-llm "Apa ketentuan perlindungan saksi?"

# Reranker BGE lokal (model diunduh sekali dari Hugging Face).
pip install -e ".[rerank]"
lexnusa-ask --backend qdrant --rerank --no-llm "Apa ketentuan perlindungan saksi?"

# Server Qdrant lokal; setelah aktif, arahkan CLI lewat environment variable.
docker compose up -d qdrant
export QDRANT_URL=http://localhost:6333
lexnusa-index --no-parse
```

Untuk Qdrant Cloud, isi `QDRANT_URL` dan `QDRANT_API_KEY`. Retrieval mengambil kandidat semantik
dari Qdrant dan kandidat kata-kunci BM25, menggabungkannya dengan Reciprocal Rank Fusion (RRF),
lalu menjalankan `BAAI/bge-reranker-v2-m3` jika opsi `--rerank` diberikan. Alias
`lexnusa-qdrant-index` tetap tersedia. Untuk jalur kompatibilitas Chroma M1, gunakan
`lexnusa-chroma-index` lalu `lexnusa-ask --backend chroma`.

## Menjalankan M4

Scraper M4 membaca status dan relasi `mengubah`/`mencabut` dari halaman detail resmi. Saat
indexing, relasi tersebut dipropagasikan ke dokumen target sehingga peraturan lama dapat ditandai
`diubah` atau `dicabut`. Bila sumber tidak menyediakan status, jawaban menyebutnya sebagai
`belum terverifikasi` dan tidak menebak.

```bash
# Ambil ulang metadata status lalu bangun ulang indeks Qdrant.
lexnusa-scrape --limit 100 --delay 2
lexnusa-index

# Lihat keputusan router dan subquery yang dijalankan.
lexnusa-ask --show-plan --no-llm \
  "Bandingkan perlindungan saksi dan perlindungan korban dalam undang-undang"

# Pertanyaan status memperluas retrieval ke relasi perubahan/pencabutan.
lexnusa-ask --show-plan --no-llm "Apakah UU Nomor 1 Tahun 2020 masih berlaku?"
```

Router berjalan lokal tanpa panggilan LLM: pertanyaan sederhana memakai satu retrieval, pertanyaan
status menambahkan query relasi, dan pertanyaan perbandingan/kompleks memakai beberapa subquery
yang hasilnya dideduplikasi. Prompt generatif dan jawaban ekstraktif sama-sama menampilkan status
setiap sumber, pasal, URL PDF resmi, dan disclaimer.

## Menjalankan M5

Jalankan API dan chat UI dari satu proses:

```bash
source .venv/bin/activate
lexnusa-api
```

Buka `http://localhost:8000`. Dokumentasi OpenAPI tersedia di `http://localhost:8000/docs`,
health check di `/health`, dan endpoint chat di `POST /api/chat`:

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"Apakah UU Nomor 1 Tahun 2020 masih berlaku?","use_llm":false}'
```

Konfigurasi runtime:

| Variabel | Fungsi | Default |
|---|---|---|
| `LEXNUSA_INDEX_DIR` | Lokasi Qdrant embedded | `data/qdrant` |
| `QDRANT_URL` | Server/Qdrant Cloud | kosong |
| `QDRANT_API_KEY` | Kredensial Qdrant Cloud | kosong |
| `GROQ_API_KEY` | Jawaban generatif opsional | kosong |
| `LEXNUSA_API_KEY` | Wajibkan header `X-API-Key` | kosong/publik |
| `LEXNUSA_RATE_LIMIT` | Maksimum request per menit per klien | `30` |

Repo menyertakan `Dockerfile` dan `render.yaml`. Untuk deployment Render, hubungkan repo sebagai
Blueprint, isi `QDRANT_URL`/`QDRANT_API_KEY`, dan tambahkan `GROQ_API_KEY` bila mode generatif
diinginkan. UI dan API sengaja disajikan dari origin yang sama agar tidak memerlukan konfigurasi
CORS atau deployment frontend terpisah.

## Catatan

**Bukan nasihat hukum.** Setiap jawaban harus tetap menampilkan sumber asli dan disclaimer
bahwa ini alat bantu pencarian, bukan pengganti konsultasi hukum resmi. Sebelum scraping
besar-besaran, cek `robots.txt` dan ketentuan penggunaan situs pemerintah terkait, dan batasi
rate request supaya tidak membebani server publik.
