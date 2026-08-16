# LexNusa — instruksi untuk AI coding agent

Baca `README.md` dulu untuk konteks produk lengkap (fitur, arsitektur, stack, roadmap).
File ini isinya cara kerja yang diharapkan saat kamu membantu membangun repo ini.

## Status saat ini

Repo ini masih **kosong / tahap blueprint** — belum ada kode. Kalau diminta "bantu bangun
sistemnya" tanpa instruksi lebih spesifik, mulai dari milestone paling awal yang belum
selesai di tabel Roadmap pada `README.md` (urutannya M0 → M6, jangan loncat).

## Prinsip kerja

- **Ikuti stack yang sudah dipilih** di README kecuali user secara eksplisit minta ganti.
  Semua komponen dipilih karena punya jalur gratis — jangan ganti ke layanan berbayar
  tanpa konfirmasi.
- **Jangan bangun semua fitur sekaligus.** Kerjakan satu milestone dalam satu waktu, buat
  sesuatu yang bisa dijalankan/di-demo di akhir tiap milestone.
- **Retrieval harus bisa diverifikasi.** Setiap jawaban akhir dari sistem wajib menyertakan
  sumber (pasal + link dokumen asli). Jangan implementasi jawaban tanpa sitasi, ini bukan
  fitur opsional — ini syarat kepercayaan produk.
- **Hormati sumber data.** Scraper harus cek `robots.txt`, pakai rate limiting, dan jangan
  bebani server pemerintah. Ini legal-tech untuk domain publik, bukan alasan untuk scraping
  serampangan.
- **Bahasa kode vs dokumentasi:** kode, nama variabel/fungsi, dan commit message dalam
  Bahasa Inggris (konvensi umum open-source). Dokumen produk (README, komentar user-facing,
  UI copy) dalam Bahasa Indonesia karena target pengguna dan sumber data lokal.

## Kalau diminta ubah arsitektur

Blueprint di README/PDF adalah rencana awal, bukan aturan mati. Kalau ada alasan teknis
kuat untuk beda pendekatan (misal Qdrant ternyata kurang cocok, atau ada API gratis yang
lebih baik), jelaskan tradeoff-nya ke user sebelum mengubah, jangan diam-diam menyimpang
dari blueprint.

## Referensi

Versi visual lengkap blueprint ada di `lexnusa-rag-blueprint.pdf` di folder yang sama.
