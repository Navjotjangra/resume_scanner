# AGENTS.md — Resume Scanner & Ranker

Read this file at the start of every session. It is short on purpose. Details live in `docs/`.

## 1. Project in one paragraph
Desktop app (Python + Tkinter). A recruiter pastes a job description (JD), adds resumes (PDF / DOCX / DOC / TXT) and clicks **Scan & Rank**. The app extracts text, vectorizes JD + resumes with **TF-IDF**, scores each resume against the JD with **cosine similarity**, and shows a ranked table with Match % and a level (Excellent / Good / Fair / Low). BCA final-year project. Scope is fixed by the approved synopsis. Do not expand it.

## 2. Docs (read only what the current task needs)
| File | Use it for |
|---|---|
| `docs/PRD.md` | What and why: features, priorities, acceptance criteria |
| `docs/TRD.md` | How: architecture, module APIs, algorithm settings, errors, tests |
| `docs/AGENT_PROMPT.md` | Phase-by-phase task list (P0–P8) |
| `docs/PROGRESS.md` | Done / next / ideas. **You maintain this file.** |

If two docs conflict, stop and ask. Do not guess.

## 3. Stack (fixed)
- Python 3.10+ · Tkinter/ttk (GUI) · scikit-learn (`TfidfVectorizer`, `cosine_similarity`)
- PyMuPDF (PDF) · python-docx (DOCX) · `threading` + `queue` (background work)
- pytest (tests) · `logging` (no `print`)
- **No new dependencies without asking.** No NLTK/spaCy, no LLM/API calls, no network, no database, no web framework.

## 4. Layout
```
resume_scanner/
├── AGENTS.md  README.md  run.py  requirements.txt  requirements-dev.txt  pytest.ini
├── docs/            PRD.md  TRD.md  AGENT_PROMPT.md  PROGRESS.md
├── scanner/         config.py models.py errors.py logging_setup.py
│                    extractors.py preprocess.py ranker.py pipeline.py exporter.py
│   └── gui/         app.py  worker.py
├── tests/
├── scripts/         evaluate.py
├── sample_data/     job_descriptions/  resumes/  (synthetic only)
└── logs/            (gitignored)
```

## 5. Commands (Windows PowerShell, from project root)
```
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python run.py          # run the app
pytest -q              # run tests
```

## 6. Architecture rules (never break)
1. Everything in `scanner/` **except `scanner/gui/`** must not import `tkinter`.
2. Only the Tkinter main thread touches widgets. The worker thread talks to the GUI through a `queue.Queue`; the GUI polls it with `root.after(...)`.
3. One bad file must never crash a scan. Collect it in `failures` with a readable reason and continue.
4. Never log resume text or personal data. Filenames only.
5. Use `pathlib.Path` for all paths.
6. Thresholds, limits, stop words and token maps live in `scanner/config.py` only. No magic numbers elsewhere.
7. Same inputs must give the same output (deterministic sort, tie-break by filename).

## 7. Code conventions
- Type hints on all public functions. Short docstrings.
- Small functions (about 40 lines max). `snake_case`. Specific exceptions from `scanner/errors.py`; no bare `except:`.
- `except Exception` is allowed only at a boundary (worker thread, per-file loop) and must call `logging.exception`.
- Tests next to every module in `tests/`. Build fixtures in `tmp_path`; do not commit binary fixtures.

## 8. Known gotchas (already decided, follow the TRD)
- sklearn's default tokenizer drops single letters and breaks `c++`, `c#`, `.net`, `node.js`. Normalize them via `TECH_TOKEN_MAP` before vectorizing.
- Do not set `max_df < 1.0`. With a tiny corpus it can empty the vocabulary and raise `ValueError`.
- `python-docx` cannot read `.doc`. Use the LibreOffice conversion path or raise `UnsupportedFormatError` with a clear message.
- `python-docx` `doc.paragraphs` skips tables. Many resumes are laid out in tables, so read table cells too.
- Scanned / image-only PDFs have no text. Report them as failures (`EmptyTextError`), never as a 0% score.
- Tkinter is not thread-safe. No widget calls from the worker.
- CSV export: `encoding="utf-8-sig"`, `newline=""` so Excel opens it correctly.
- PyMuPDF import: `try: import pymupdf as fitz` / `except ImportError: import fitz`.

## 9. Working protocol (every task)
1. Read this file plus only the TRD/PRD sections the task names.
2. State a plan in 5 bullets or fewer, then wait for approval if running in Plan mode.
3. Make the smallest change that satisfies the task. Do not refactor unrelated code.
4. Write or update tests. Run `pytest -q`. For GUI work, also run `python run.py` and say what you checked.
5. Update `docs/PROGRESS.md` (tick the phase, note decisions, add out-of-scope ideas under "Ideas").
6. Reply with: files changed, test result, suggested commit message.
7. **Stop.** Do not start the next phase.

## 10. Definition of done
- `pytest -q` passes. App starts with `python run.py` without errors (once GUI exists).
- No new dependency, no network call, no resume text in logs.
- Acceptance criteria for the touched requirements in `docs/PRD.md` are met.
- `docs/PROGRESS.md` updated.

## 11. Out of scope (add to "Ideas" in PROGRESS.md, do not build)
OCR, embeddings/LLMs, skill taxonomy, web UI, user accounts, database, cloud, bias auditing, multi-language resumes.
