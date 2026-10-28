# AGENT_PROMPT.md — Build prompts for Resume Scanner & Ranker

Written for Cline in VS Code. It works the same with Claude Code, Copilot Agent or Cursor: paste the prompts as-is.

## How to use
1. Put `AGENTS.md` in the project root and `PRD.md`, `TRD.md`, this file in `docs/`.
2. Start a **new task/chat for every phase**. Small context windows forget; a fresh task plus `AGENTS.md` fixes that.
3. Paste the **Master prompt** once, then the **phase prompt**. Use **Plan mode** first, review the plan, then switch to **Act mode**.
4. After each phase: run `pytest -q`, run the app (from P5), read the diff, commit, then start the next phase.
5. Model choice: a small local model (for example `qwen2.5-coder:7b`) is fine for P0, P1, P2, P4, P8. Use the strongest model you have free access to for **P3 (ranker)** and **P6 (GUI threading)**.
6. If the agent drifts, use the **Recovery prompts** at the bottom.

---

## Master prompt (paste first in every new task)
```text
You are a senior Python engineer helping a BCA student build "Resume Scanner & Ranker"
(Tkinter desktop app, TF-IDF + cosine similarity) in the current VS Code workspace.

Before doing anything:
1. Read AGENTS.md fully. Its rules override your defaults.
2. Read ONLY the docs sections that my task names (docs/PRD.md, docs/TRD.md).
3. Read docs/PROGRESS.md to see what is already done.

Rules:
- Do exactly the phase I give you. Do not start the next phase.
- No new dependencies, no network/API calls, no extra features. If you have an idea, add it
  under "Ideas" in docs/PROGRESS.md instead of building it.
- Keep diffs small. Do not rewrite files you were not asked to touch.
- If the docs conflict or something is unclear, ask me one short question before coding.
- Never log or print resume contents.
- Finish by: listing files changed, showing the pytest result, updating docs/PROGRESS.md,
  and giving me a one-line commit message. Then stop.

Reply "READY" and wait for the phase prompt.
```

---

## P0 — Scaffold
```text
Phase P0: project scaffold. Read AGENTS.md, TRD §3, §4, §14.

Create ONLY the skeleton, with no business logic:
1. Folders and files exactly as in AGENTS.md §4. Empty modules get a module docstring only.
2. requirements.txt (scikit-learn, PyMuPDF, python-docx), requirements-dev.txt (-r requirements.txt, pytest),
   pytest.ini (testpaths = tests, pythonpath = .), .gitignore (.venv, __pycache__, .pytest_cache, logs/,
   dist/, build/, *.spec, sample_data/resumes/real/), README.md stub with the project title.
3. scanner/config.py with every constant from TRD §14 (use MatchLevel names via a small helper later; plain strings are fine now).
4. scanner/errors.py and scanner/models.py exactly as TRD §4.
5. scanner/logging_setup.py per TRD §5.2.
6. docs/PROGRESS.md: checklist P0..P8 (P0 ticked), a "Decisions" section, an "Ideas" section, and a "GUI manual checklist" section (empty).
7. tests/test_smoke.py: imports scanner.config, scanner.models, scanner.errors.
8. tests/test_architecture.py: fails if any scanner/*.py outside scanner/gui imports tkinter.

Do NOT create a virtual environment or install packages. I will do that.
Done when: pytest -q passes after I install requirements. Tell me the exact commands to run.
```

## P1 — Text extraction
```text
Phase P1: text extraction. Read AGENTS.md §8, TRD §5.3, §6, §7 (test_extractors.py row).

Implement scanner/extractors.py exactly per TRD §5.3:
- extract_text(path) with the 5-step behavior (exists, extension, size, dispatch, empty check).
- PDF via PyMuPDF (pymupdf import with fitz fallback), password-protected -> ExtractionError.
- DOCX via python-docx: body paragraphs AND all table cells.
- TXT with the encoding fallback order from the TRD.
- DOC best effort through LibreOffice (soffice) with temp dir and timeout; otherwise UnsupportedFormatError
  with the exact message from the TRD.

Write tests/test_extractors.py covering every case in the TRD §7 table. Create fixtures inside tmp_path
(python-docx for .docx including a table, PyMuPDF for .pdf, plain files for txt). No binary files in the repo.
Monkeypatch shutil.which for the .doc test; do not require LibreOffice.

Done when: pytest -q is green. Do not touch other modules.
```

## P2 — Preprocessing
```text
Phase P2: preprocessing. Read TRD §5.4 and §14 (TECH_TOKEN_MAP, SYNONYMS).

Implement scanner/preprocess.py: normalize_text(text) following the 7 steps in TRD §5.4 in that exact order.
Pre-compile regexes at module level. All maps come from config.py.

Write tests/test_preprocess.py: c++ / c# / .net / node.js survive as single tokens, URL/email/phone removed,
standalone numbers removed but "python3" kept, synonyms expanded ("ML" -> "machine learning"),
idempotent, empty and whitespace-only input return "".

Done when: pytest -q is green.
```

## P3 — Ranker (use your strongest model)
```text
Phase P3: TF-IDF + cosine ranker. Read TRD §5.5, §14, and §7 (test_ranker.py row).

Implement scanner/ranker.py: build_vectorizer, level_for, top_matching_terms, rank_resumes, exactly as TRD §5.5.
Hard rules:
- TfidfVectorizer settings from TRD only. Do NOT set max_df or min_df.
- Fit on [jd] + resumes together. Cosine via sklearn cosine_similarity.
- Deterministic sort: (-score, filename.lower()). Ranks are sequential 1..N.
- Empty vocabulary or a JD with zero non-zero terms -> InvalidJobDescriptionError.
- level_for uses LEVEL_THRESHOLDS from config and returns MatchLevel.

Write tests/test_ranker.py with every case in the TRD §7 table. Use small inline strings
(e.g. a Python/ML JD, one matching resume, one cooking-chef resume) so tests are fast and readable.

Done when: pytest -q is green. In your final message, print the scores of the sample test so I can see them.
```

## P4 — Pipeline and CSV export
```text
Phase P4: pipeline and exporter. Read TRD §5.6, §5.7, §6, §7 (pipeline + exporter rows).

Implement scanner/pipeline.py scan_and_rank(...) and scanner/exporter.py export_csv(...) per the TRD.
Rules: sequential extraction, per-file failure collection, ScanCancelled when the Event is set,
progress callback called once per file, duplicate paths collapsed, no ranker call when nothing extracted.

Write tests/test_pipeline.py and tests/test_exporter.py per TRD §7 (build files in tmp_path).
Done when: pytest -q is green.
```

## P5 — GUI skeleton (layout only)
```text
Phase P5: GUI skeleton. Read PRD §8 (layout) and TRD §5.8, §12.

Create scanner/gui/app.py with MainWindow and main(), and run.py as the entry point.
Build ALL widgets from TRD §5.8 and lay them out as in the PRD wireframe (ttk, grid, resizable,
minimum size 900x650, fits 1366x768).
Wire only these behaviors for now: JD Clear and Load .txt, Add Files, Add Folder (non-recursive,
supported extensions only, duplicates ignored), Remove, Clear all, resume counter, status bar messages.
Scan, Cancel and Export buttons exist but do nothing yet (Cancel and Export disabled).

No business logic, no threading yet. Do not import ranker/pipeline here.
Done when: `python run.py` opens a clean window and I can add/remove files. Tell me what to click to verify.
```

## P6 — GUI wiring and threading (use your strongest model)
```text
Phase P6: connect the GUI to the pipeline. Read TRD §5.8 (threading protocol), §6, and AGENTS.md §6 rules 2 and 3.

1. Create scanner/gui/worker.py: the message dataclasses (Progress, Finished, Failed, Cancelled) and ScanWorker(threading.Thread, daemon=True).
2. In app.py: validate inputs (JD present, at least one resume) -> start ScanWorker with a queue.Queue and a threading.Event.
3. Implement _poll_queue with root.after(QUEUE_POLL_MS) that drains the queue and updates:
   progress bar + "n / N" label, status bar, Ranking tab (Treeview with level color tags), Skipped tab (with count in tab title),
   detail label for the selected row (full path + top terms).
4. While scanning: disable Scan and add/remove buttons, enable Cancel. After finish/cancel/fail: restore state.
5. Export CSV via filedialog + exporter.export_csv; enabled only when results exist.
6. Column-header click sorts the Ranking table.
7. Closing the window during a scan sets the cancel event first.

Rules: the worker thread must never touch a widget. Handle Failed(message) with a messagebox.
Done when: scanning 20+ files does not freeze the window, Cancel works, Export opens in Excel, a corrupt file shows up in Skipped.
Add the manual GUI checklist to docs/PROGRESS.md and tick what you could verify by running the app.
```

## P7 — Hardening, sample data, evaluation
```text
Phase P7: hardening and evaluation. Read PRD §9, §10, TRD §8, §9, §10.

1. Create synthetic sample data: sample_data/job_descriptions/ (3 JDs: data analyst, ML engineer, web developer)
   and sample_data/resumes/ with 24 SHORT synthetic .txt resumes (mix of strong, partial and irrelevant matches,
   including one using C++/C#/.NET). Fake names only. No real personal data.
2. Create sample_data/eval/labels_<jd>.csv templates (filename,grade) with grade left blank. I will fill them by hand.
3. Implement scripts/evaluate.py per TRD §10 (Spearman, Precision@5, random baseline with fixed seed,
   keyword-overlap baseline, --sweep for threshold candidates). Use scipy.stats.spearmanr.
4. Add a test for the evaluate helpers where possible (pure functions).
5. Add the MAX_RESUMES warning and a check in the GUI for it. Re-read the error matrix in TRD §6 and confirm each row is handled.

Do NOT invent labels or results. Do NOT change LEVEL_THRESHOLDS yourself: print the sweep and I will decide.
Done when: pytest -q is green and `python scripts/evaluate.py ...` runs on the sample data once I fill the labels.
```

## P8 — README, report notes, optional packaging
```text
Phase P8: documentation. Read PRD §11, §12 and TRD §11.

1. README.md: what it is, screenshot placeholders, install (Windows PowerShell), run, usage steps, supported formats,
   .doc note (LibreOffice), limitations (from PRD §11), privacy note, "ranking aid, not a hiring decision" disclaimer, how to run tests and evaluation.
2. docs/REPORT_NOTES.md: bullet material for my project report: architecture diagram as a Mermaid block,
   algorithm flow, the sklearn smoothed-IDF note, module list with one-line purposes, test summary table,
   an empty "Evaluation results" table for me to fill, limitations and future work.
3. Optional (ask me first): PyInstaller build per TRD §11.

Do not claim results you did not measure. Done when: README commands work on a clean checkout.
```

---

## Recovery prompts

**Agent started the next phase or added features**
```text
Stop. You went beyond the phase. Revert everything outside the phase scope, move extra ideas to "Ideas" in
docs/PROGRESS.md, then show me only the in-scope diff.
```

**Tests failing in a loop (more than 2 attempts)**
```text
Stop editing. Print the failing test name, the full error, and the exact lines under test. Give me a
2-sentence diagnosis and your single best fix. Wait for my approval before changing anything.
```

**Agent forgot the rules or context got long**
```text
Re-read AGENTS.md and docs/PROGRESS.md now. Then tell me in 5 bullets: current phase, what is done,
what is left, which files you will touch, which rules apply. Wait for my go-ahead.
```

**GUI freezes or Tkinter errors from a thread**
```text
Audit scanner/gui/ for any widget access outside the main thread. List each violation with file and line.
Fix them by posting messages to the queue only. Do not change pipeline/ranker code.
```

**Agent wants a new library**
```text
No new dependencies. Solve it with the allowed stack in AGENTS.md §3, or tell me the trade-off and wait.
```
