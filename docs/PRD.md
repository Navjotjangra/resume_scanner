# PRD — Resume Scanner & Ranker

Version 1.0 · Owner: Navjot · Type: BCA final-year project (desktop app) · Source: approved synopsis

## 1. Overview
A desktop application that scans many resumes, compares each against a job description (JD) using TF-IDF and cosine similarity, and ranks them by match percentage. It reduces the time a recruiter spends on first-pass screening.

## 2. Problem
Manual screening of hundreds of resumes is slow, inconsistent and tiring. Skills get overlooked, formats differ (PDF/DOCX/DOC/TXT), and ranking by hand is subjective. Recruiters need a fast, repeatable first-pass ranking they can then review.

## 3. Goals and non-goals
**Goals**
- G1. Rank a batch of resumes against one JD in seconds.
- G2. Support PDF, DOCX, DOC (best effort) and TXT.
- G3. Show a clear Match % and level per resume, and *why* (top matching keywords).
- G4. Never freeze or crash on a bad file.
- G5. Demonstrate NLP/ML concepts clearly (TF-IDF, cosine similarity) with a measured evaluation.

**Non-goals**
- Not a hiring decision tool. Output is a ranking aid; a human reviews the result.
- No semantic/LLM matching, OCR, accounts, database, cloud or web UI in v1.

## 4. Users
| User | Need |
|---|---|
| HR recruiter (primary) | Paste JD, load resumes, get a ranked list fast, export it |
| Project evaluator / guide (secondary) | See a working demo, understand the algorithm, see measured results |

## 5. User stories
- US1. As a recruiter, I paste a JD and add 50 resumes so I can see the best matches first.
- US2. As a recruiter, I see which keywords drove each score so I can trust or question it.
- US3. As a recruiter, I see which files could not be read and why, so I can fix them.
- US4. As a recruiter, I export the ranking to CSV to share with my team.
- US5. As an evaluator, I can see the evaluation results comparing the system to simple baselines.

## 6. Functional requirements
Priority: **M** must · **S** should · **C** could

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-01 | Paste JD into a multi-line text box | M | Empty or keyword-less JD blocks the scan with a clear message |
| FR-02 | Load JD from a `.txt` file | S | File content appears in the box; bad encoding handled |
| FR-03 | Add resumes via file dialog (multi-select) | M | Accepts `.pdf .docx .doc .txt`; others ignored with a message |
| FR-04 | Add all supported files from a folder | S | Non-recursive; count shown |
| FR-05 | Remove selected / clear all resumes; ignore duplicate paths | M | List and counter update correctly |
| FR-06 | Extract text from PDF, DOCX (incl. tables), TXT | M | Text returned for valid files; errors become per-file failures |
| FR-07 | `.doc` support, best effort | S | Works when LibreOffice is installed; otherwise a clear "convert to .docx" message |
| FR-08 | Preprocess text (normalize, clean, tech-term handling) | M | `c++`, `c#`, `.net`, `node.js` survive; URLs/emails/phones removed |
| FR-09 | TF-IDF vectorization + cosine similarity vs JD | M | Score in 0–1 per resume; identical text scores about 100% |
| FR-10 | Rank descending; ties broken by filename | M | Same inputs give identical order every run |
| FR-11 | Show Match % (1 decimal) and level Excellent/Good/Fair/Low | M | Level follows thresholds in `config.py` |
| FR-12 | Ranking table: Rank, File, Match %, Level, Top keywords | M | Colored by level |
| FR-13 | Scan runs in a background thread with progress and status bar | M | Window stays responsive; progress shows n/N |
| FR-14 | Per-file error handling; "Skipped" tab with reasons | M | One bad file never stops the scan |
| FR-15 | Cancel a running scan | S | Stops within about 1 file; UI returns to idle |
| FR-16 | Top matching keywords per resume (detail view) | S | Up to 8 terms, from JD×resume term weights |
| FR-17 | Export results to CSV | S | Opens correctly in Excel (UTF-8 BOM) |
| FR-18 | Open selected resume in the default viewer | C | Double-click row |
| FR-19 | Level thresholds editable | C | Via `config.py` only |

## 7. Non-functional requirements
- **Performance (targets, verify on your machine):** 50 resumes of about 2 pages each ranked in 10 s or less on the recommended hardware. UI never blocks longer than about 200 ms.
- **Usability:** Fits 1366×768. One main screen. Plain-language errors.
- **Portability:** Windows 10/11 primary; Linux/macOS should run (Tkinter + pure-Python deps).
- **Reliability:** No unhandled exception reaches the user. Failures are logged and shown.
- **Privacy:** Fully offline. No resume text in logs. Sample data is synthetic.
- **Determinism:** Same inputs give the same ranking.
- **Maintainability:** Core logic has no GUI imports and is unit-tested.

## 8. Screen layout
```
┌────────────────────────────────────────────────────────────────┐
│ Resume Scanner & Ranker                                        │
├────────────────────────────────────────────────────────────────┤
│ Job Description                      [Load .txt] [Clear]       │
│ ┌────────────────────────────────────────────────────────────┐ │
│ │ multi-line text area                                       │ │
│ └────────────────────────────────────────────────────────────┘ │
│ Resumes (12)     [Add Files] [Add Folder] [Remove] [Clear all] │
│ ┌────────────────────────────────────────────────────────────┐ │
│ │ file list                                                  │ │
│ └────────────────────────────────────────────────────────────┘ │
│ [ Scan & Rank ] [ Cancel ]   ▓▓▓▓▓░░░░░  5 / 12               │
│ [ Ranking ] [ Skipped (1) ]                       [Export CSV] │
│ ┌──Rank─┬─File──────────┬─Match %─┬─Level─────┬─Top keywords─┐ │
│ │   1   │ a.pdf         │  52.3   │ Excellent │ python, ...  │ │
│ └───────┴───────────────┴─────────┴───────────┴──────────────┘ │
│ Status: Done. 12 ranked, 1 skipped.                            │
└────────────────────────────────────────────────────────────────┘
```

## 9. Match levels
Level is derived from Match % (cosine × 100) using thresholds in `config.py`.

| Level | Initial threshold |
|---|---|
| Excellent | ≥ 40 |
| Good | ≥ 25 |
| Fair | ≥ 12 |
| Low | below 12 |

These are **starting guesses**. TF-IDF cosine scores between a short JD and a long resume are usually low, so absolute cut-offs must be calibrated on the evaluation set (Phase P7). Report the final values and how you chose them.

## 10. Success metrics and evaluation plan
- Build an evaluation set: 1–3 JDs × 20–30 resumes. Use synthetic resumes or a public dataset; do not use real people's resumes without consent.
- Label each resume 0–3 against each JD (0 irrelevant, 3 strong match) by hand.
- Metrics: **Spearman ρ** (system score vs human label) and **Precision@5**.
- Baselines to beat: (a) random order (seeded), (b) raw keyword-overlap count.
- Report honestly, including failure cases. There is no fixed pass mark; the point is a measured, explainable result better than the baselines.

## 11. Risks and limitations (state these in the report)
| Risk | Effect | Mitigation |
|---|---|---|
| Keyword matching has no semantics | "ML" vs "machine learning", synonyms missed | Small synonym map; list as future work |
| Keyword stuffing | Inflated scores | Sublinear TF; human review; note as limitation |
| Tiny corpus makes IDF noisy | Unstable weights with few resumes | Fit on JD + resumes; document it |
| Scanned PDFs, odd layouts | No or messy text | Report as skipped, never score 0 |
| `.doc` needs a converter | Some files unreadable | LibreOffice path + clear message |
| Bias in resume text (college, location) | Unfair proxies | Disclaimer in UI/README; human decides |

## 12. Future work (outside synopsis; do not build in v1)
Skill-taxonomy extraction and a hybrid score, sentence-embedding similarity, OCR for scanned PDFs, resume section parsing, web UI, saved history.

## 13. Milestones
| Phase | Deliverable |
|---|---|
| P0 | Scaffold, config, models, errors |
| P1 | Text extraction + tests |
| P2 | Preprocessing + tests |
| P3 | TF-IDF/cosine ranker + tests |
| P4 | Pipeline + CSV export + tests |
| P5 | GUI skeleton |
| P6 | GUI wiring, threading, progress, details, export |
| P7 | Hardening, sample data, evaluation, threshold calibration |
| P8 | README, report notes, optional packaging |
