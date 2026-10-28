# Resume Scanner & Ranker

Desktop application (Python + Tkinter) that scans many resumes, compares each
against a job description (JD) using **TF-IDF** and **cosine similarity**, and
ranks them by match percentage. BCA final-year project.

It reduces the time a recruiter spends on first-pass screening by surfacing the
best-matching resumes first, with match percentage, level (Excellent / Good /
Fair / Low), and the top keywords that drove each score.

---

## Screenshots

*(Add screenshots here)*

| Screen | Placeholder |
|--------|-------------|
| Main window with JD, resume list, and results | `docs/screenshots/main_window.png` |
| Ranking table colored by level | `docs/screenshots/ranking_tab.png` |
| Skipped tab with per-file failure reasons | `docs/screenshots/skipped_tab.png` |

---

## Stack (fixed by synopsis)

- **Python 3.10+**
- **GUI:** Tkinter + ttk (ships with python.org installers)
- **ML:** scikit-learn (`TfidfVectorizer`, `cosine_similarity`)
- **PDF:** PyMuPDF
- **DOCX:** python-docx (paragraphs + table cells)
- **Concurrency:** `threading` + `queue.Queue` (background scan, responsive UI)
- **Tests:** pytest

**No network, no LLM, no OCR, no database.** Fully offline.

---

## Install (Windows PowerShell, from project root)

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

After the first successful install, run `pip freeze` and pin the versions you tested.

---

## Run

```powershell
python run.py
```

The window opens with a minimum size of 900×650 and fits a 1366×768 screen.

---

## Usage steps

1. **Paste a job description** into the multi-line text box (or click **Load .txt** to load one from a file).
2. **Add resumes** via **Add Files** (multi-select) or **Add Folder** (non-recursive). Supported formats: `.pdf`, `.docx`, `.doc`, `.txt`.
3. **Remove** unwanted files or **Clear all** as needed. The counter shows how many resumes are queued.
4. Click **Scan & Rank**. A background worker extracts text, ranks resumes, and updates the progress bar (n/N). The window stays responsive.
5. Review the **Ranking** tab: Rank, File, Match %, Level (colored), Top keywords. Click a column header to sort. Select a row to see the full path and top terms.
6. Review the **Skipped (n)** tab for files that could not be read and why.
7. Click **Export CSV** to save the ranking (UTF-8 with BOM, opens correctly in Excel).
8. Click **Cancel** to stop a running scan.

---

## Supported formats

| Format | Notes |
|--------|-------|
| `.pdf` | Text-based PDFs via PyMuPDF. Scanned/image-only PDFs are reported as skipped (never scored 0%). |
| `.docx` | Body paragraphs **and** table cells (including nested tables). |
| `.doc` | Best effort via LibreOffice (`soffice`). If LibreOffice is not installed, you get a clear message to convert the file to `.docx` manually. |
| `.txt` | UTF-8, UTF-16 (BOM), cp1252, latin-1 fallback. |

---

## Match levels

Level is derived from Match % (cosine × 100) using thresholds in `scanner/config.py`:

| Level | Threshold |
|-------|-----------|
| Excellent | ≥ 40 |
| Good | ≥ 25 |
| Fair | ≥ 12 |
| Low | below 12 |

These are starting guesses; calibrate on your evaluation data (Phase P7).

---

## Limitations (from PRD §11)

- Keyword matching has no semantics: "ML" vs "machine learning" and synonyms may be missed (a small synonym map is included).
- Keyword stuffing can inflate scores; output is a ranking aid, not a hiring decision.
- Tiny corpora make IDF noisy; results are fit on the JD + resumes together.
- Scanned PDFs and odd layouts may produce no or messy text — reported as skipped.
- `.doc` requires LibreOffice; otherwise convert to `.docx`.
- Bias in resume text (college, location, etc.) can be an unfair proxy — a human always decides.

---

## Privacy

- Fully offline. No network calls anywhere.
- No resume text or JD text is written to logs (only filenames, counts, and timings).
- Sample data in `sample_data/` is synthetic (fake names only).

---

## Disclaimer

This tool is a **ranking aid, not a hiring decision tool**. Output should be reviewed by a human. The scores reflect keyword overlap via TF-IDF cosine similarity, not candidate suitability.

---

## Run tests

```powershell
pytest -q
```

Tests live in `tests/` and cover extractors, preprocessing, ranker, pipeline, exporter, evaluation helpers, and the architecture rule (no `tkinter` outside `scanner/gui/`).

---

## Run evaluation

```powershell
python scripts/evaluate.py --jd sample_data/job_descriptions/data_analyst.txt `
    --resumes-dir sample_data/resumes `
    --labels sample_data/eval/labels_data_analyst.csv
```

Outputs a markdown table comparing **system** (TF-IDF + cosine), **random** (fixed seed), and **keyword-overlap** baselines using Spearman ρ and Precision@5.

To calibrate level thresholds, run:

```powershell
python scripts/evaluate.py --sweep --jd sample_data/job_descriptions/data_analyst.txt `
    --resumes-dir sample_data/resumes
```

*(Fill in the grades in `sample_data/eval/labels_*.csv` by hand before evaluating.)*

---

## Project structure

```
resume_scanner/
├── AGENTS.md  README.md  run.py  requirements.txt  requirements-dev.txt  pytest.ini
├── docs/            PRD.md  TRD.md  AGENT_PROMPT.md  PROGRESS.md  REPORT_NOTES.md
├── scanner/         config.py  models.py  errors.py  logging_setup.py
│                    extractors.py  preprocess.py  ranker.py  pipeline.py  exporter.py
│   └── gui/         app.py  worker.py
├── scripts/         evaluate.py
├── sample_data/     job_descriptions/  resumes/  eval/          (synthetic only)
├── tests/           test_*.py
└── logs/            (gitignored)
```

---

## Milestones

| Phase | Deliverable | Status |
|-------|-------------|--------|
| P0 | Scaffold, config, models, errors | Done |
| P1 | Text extraction + tests | Done |
| P2 | Preprocessing + tests | Done |
| P3 | TF-IDF/cosine ranker + tests | Done |
| P4 | Pipeline + CSV export + tests | Done |
| P5 | GUI skeleton | Done |
| P6 | GUI wiring, threading, progress, details, export | Done |
| P7 | Hardening, sample data, evaluation, threshold calibration | Done |
| P8 | README, report notes, optional packaging | Done |
