# Progress — Resume Scanner & Ranker

## Checklist
- [x] P0 Scaffold
- [x] P1 Text extraction + tests
- [x] P2 Preprocessing + tests
- [x] P3 TF-IDF/cosine ranker + tests
- [x] P4 Pipeline + CSV export + tests
- [x] P5 GUI skeleton
- [x] P6 GUI wiring, threading, progress, details, export
- [x] P7 Hardening, sample data, evaluation, threshold calibration
- [x] P8 README, report notes, optional packaging

## Decisions
- P7: MAX_RESUMES warning added in GUI (_add_path blocks at 500, messagebox shown).
- P7: evaluate.py uses scipy.stats.spearmanr, fixed-seed random baseline (seed=42), keyword-overlap baseline; --sweep prints level distribution.
- P7: All TRD §6 error matrix rows verified as handled (empty JD, no resumes, unsupported ext, .doc w/o LibreOffice, oversize, corrupt PDF, empty/scanned file, cancel, unexpected exception).

## Ideas
(None yet)

## GUI manual checklist
- [x] Window opens cleanly (python run.py), minsize 900x650, resizable
- [x] JD Load .txt and Clear work
- [x] Add Files (multi-select), Add Folder (non-recursive), supported extensions only, duplicates ignored
- [x] Remove and Clear all work; counter updates correctly
- [x] Scan starts, disables Scan + add/remove, enables Cancel; progress bar + n/N updates
- [x] Scan completes: Ranking tab populated with level-colored rows, Skipped tab with count in title
- [x] Detail label shows full path + top terms for selected row
- [x] Cancel works during scan
- [x] Export CSV enabled only when results exist; writes UTF-8 BOM CSV
- [x] Column-header click sorts the Ranking table
- [x] Closing window during a scan sets cancel event first
- [ ] Scanning 20+ files does not freeze the window (verified pattern, not yet with 20+ files)
- [ ] A corrupt file shows up in Skipped (verifiable via pipeline, not yet via GUI)
