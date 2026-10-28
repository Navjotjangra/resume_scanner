# TRD — Resume Scanner & Ranker

Version 1.0 · Implements `docs/PRD.md` · Section numbers are referenced by `AGENT_PROMPT.md`

## 1. Tech stack
| Area | Choice | Note |
|---|---|---|
| Language | Python 3.10+ | Synopsis says "3.x" |
| GUI | Tkinter + ttk | Ships with python.org installers |
| ML | scikit-learn | `TfidfVectorizer`, `cosine_similarity` |
| PDF | PyMuPDF | Import as `pymupdf`, fall back to `fitz` |
| DOCX | python-docx | Paragraphs **and** tables |
| Concurrency | `threading`, `queue` | One worker thread per scan |
| Tests | pytest | `pytest.ini`: `testpaths=tests`, `pythonpath=.` |
| Optional | LibreOffice (`soffice`) | Only for `.doc` conversion |

`requirements.txt`: `scikit-learn`, `PyMuPDF`, `python-docx`. `requirements-dev.txt`: `-r requirements.txt`, `pytest`. After the first successful install, run `pip freeze` and pin the versions you tested.

## 2. Architecture
```
┌────────────── scanner/gui (Tkinter, main thread only) ──────────────┐
│ app.py: MainWindow  ◄── queue.Queue ◄──  worker.py: ScanWorker      │
└───────────────┬──────────────────────────────────┬──────────────────┘
                │ start(jd, paths, cancel_event)   │ calls
                ▼                                  ▼
            scanner/pipeline.py  scan_and_rank()  (no GUI imports)
                │                │
                ▼                ▼
        extractors.py       preprocess.py ──► ranker.py (TF-IDF + cosine)
                                                     │
                                         models.py ◄─┴─► exporter.py
```
Rule: arrows only point downward. `scanner/` outside `gui/` never imports `tkinter`.

Scan flow:
1. Click **Scan & Rank** → GUI validates inputs → starts `ScanWorker`.
2. Worker calls `pipeline.scan_and_rank(jd, paths, on_progress, cancel)`.
3. Pipeline extracts each file (collecting failures), then ranks the successes.
4. Worker posts `Progress`, then `Finished(report)` / `Failed(msg)` / `Cancelled` to the queue.
5. GUI polls the queue every `QUEUE_POLL_MS` and updates widgets.

## 3. Folder structure
See `AGENTS.md` §4. Create empty modules with a docstring first; fill them phase by phase.

## 4. Data models (`scanner/models.py`, `scanner/errors.py`)
```python
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

class MatchLevel(str, Enum):
    EXCELLENT = "Excellent"
    GOOD = "Good"
    FAIR = "Fair"
    LOW = "Low"

@dataclass(frozen=True)
class ExtractedResume:
    path: Path
    text: str

@dataclass(frozen=True)
class FileFailure:
    path: Path
    reason: str            # human-readable, shown in the Skipped tab

@dataclass(frozen=True)
class RankedResume:
    rank: int              # 1-based, sequential
    path: Path
    score: float           # cosine, 0..1, rounded to 6 dp
    percent: float         # score*100, 1 dp
    level: MatchLevel
    top_terms: tuple[str, ...]

@dataclass(frozen=True)
class ScanReport:
    ranked: list[RankedResume]
    failures: list[FileFailure]
    elapsed_s: float
```
Exceptions (all subclass `ScannerError(Exception)`): `UnsupportedFormatError`, `FileTooLargeError`, `ExtractionError`, `EmptyTextError`, `InvalidJobDescriptionError`, `ScanCancelled`.

## 5. Module specs

### 5.1 `config.py` — see §14 for values.

### 5.2 `logging_setup.py`
`setup_logging() -> None`: rotating file handler at `logs/resume_scanner.log` (create folder), plus console. Level INFO. Log filenames, counts and timings only. Never log extracted text.

### 5.3 `extractors.py`
```python
def extract_text(path: Path) -> str: ...
def _extract_pdf(path: Path) -> str: ...
def _extract_docx(path: Path) -> str: ...
def _extract_txt(path: Path) -> str: ...
def _extract_doc(path: Path) -> str: ...
```
`extract_text` behavior, in order:
1. Path must exist and be a file, else `ExtractionError`.
2. Extension (lower-case) must be in `SUPPORTED_EXTENSIONS`, else `UnsupportedFormatError`.
3. Size above `MAX_FILE_MB` → `FileTooLargeError`.
4. Dispatch by extension. Wrap library errors (corrupt file etc.) as `ExtractionError("Could not read file: <short reason>")`; keep the original with `from e`.
5. Strip the result. Fewer than `MIN_TEXT_CHARS` characters → `EmptyTextError("No readable text (scanned or image-only file?)")`.

Details:
- **PDF:** `with fitz.open(path) as doc:`. If `doc.needs_pass` → `ExtractionError("Password-protected PDF")`. Join `page.get_text("text")` for all pages with `\n`.
- **DOCX:** `Document(path)`. Collect `paragraph.text` for body paragraphs, then every cell text in every table (also nested-table cells if present). Join with `\n`.
- **TXT:** read bytes. If it starts with a UTF-16 BOM, decode UTF-16. Else try `utf-8-sig`, then `cp1252`, then `latin-1` with `errors="replace"`.
- **DOC (best effort):** find `soffice` via `shutil.which("soffice")` or the paths in `SOFFICE_CANDIDATES`. If found: `subprocess.run([soffice, "--headless", "--convert-to", "docx", "--outdir", tmpdir, str(path)], timeout=SOFFICE_TIMEOUT_S, capture_output=True)` in a `tempfile.TemporaryDirectory`, then `_extract_docx` on the output. If not found or conversion fails → `UnsupportedFormatError(".doc needs LibreOffice installed, or save the file as .docx")`. A Word-COM path (pywin32) is a later optional enhancement, not part of v1.

### 5.4 `preprocess.py`
```python
def normalize_text(text: str) -> str: ...
```
Pipeline, in this order:
1. `unicodedata.normalize("NFKC", text)`; lower-case.
2. Remove URLs (`https?://\S+|www\.\S+`), emails, phone-like numbers (`\+?\d[\d\s().-]{8,}\d`).
3. Apply `TECH_TOKEN_MAP` (regex → replacement), e.g. `c++` → `cplusplus`.
4. Replace every character that is not `a-z`, `0-9` or whitespace with a space.
5. Apply `SYNONYMS` as whole-word replacements (`\bml\b` → `machine learning`).
6. Remove standalone numbers (`\b\d+\b`). Keep tokens like `python3`.
7. Collapse whitespace; strip.

Must be idempotent: `normalize_text(normalize_text(x)) == normalize_text(x)`. No stemming, no NLTK.

### 5.5 `ranker.py`
```python
def build_vectorizer() -> TfidfVectorizer
def level_for(percent: float) -> MatchLevel
def rank_resumes(jd_text: str, resumes: Sequence[ExtractedResume]) -> list[RankedResume]
def top_matching_terms(jd_row, resume_row, feature_names, k: int = TOP_TERMS) -> tuple[str, ...]
```
`build_vectorizer`:
```python
from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS
TfidfVectorizer(
    stop_words=sorted(ENGLISH_STOP_WORDS | EXTRA_STOPWORDS),
    ngram_range=TFIDF_NGRAM_RANGE,    # (1, 2)
    sublinear_tf=TFIDF_SUBLINEAR_TF,  # True
)   # leave max_df / min_df at defaults
```
`rank_resumes`:
1. Normalize JD and each resume with `normalize_text`.
2. `matrix = vectorizer.fit_transform([jd, *docs])`. `ValueError` (empty vocabulary) → `InvalidJobDescriptionError`.
3. `jd_vec = matrix[0]`; if `jd_vec.nnz == 0` → `InvalidJobDescriptionError("Job description has no meaningful keywords")`.
4. `scores = cosine_similarity(jd_vec, matrix[1:]).ravel()`; round to 6 dp.
5. Sort by `(-score, path.name.lower())`; assign ranks 1..N.
6. `percent = round(score * 100, 1)`; `level = level_for(percent)`.
7. `top_terms` from `top_matching_terms` using `jd_vec.multiply(resume_vec)`; take the largest non-zero entries; map column index → `get_feature_names_out()`. Nice to have: skip a unigram already contained in a listed bigram.

Notes for the report: scikit-learn uses a smoothed IDF, `idf(t) = ln((1+n)/(1+df(t))) + 1`, and L2-normalizes rows, so cosine similarity equals the dot product of the two normalized vectors. This differs slightly from the textbook formula in the synopsis; mention it.

### 5.6 `pipeline.py`
```python
ProgressFn = Callable[[int, int, str], None]   # done, total, filename

def scan_and_rank(
    jd_text: str,
    paths: Sequence[Path],
    on_progress: ProgressFn | None = None,
    cancel: threading.Event | None = None,
) -> ScanReport
```
1. Validate JD: `len(normalize_text(jd_text)) >= MIN_JD_CHARS`, else `InvalidJobDescriptionError`.
2. De-duplicate paths (resolve, keep order).
3. For each path: if `cancel` is set → raise `ScanCancelled`. Try `extract_text`. `ScannerError` → `FileFailure(path, str(e))`. Any other `Exception` → `logging.exception`, then `FileFailure(path, "Unexpected error while reading file")`. Call `on_progress(i, total, name)`.
4. If no resume was extracted, return a report with `ranked=[]` and the failures (do not call the ranker).
5. Call `rank_resumes`. Return `ScanReport` with `elapsed_s` from `time.perf_counter()`.

Extraction stays sequential (PyMuPDF is not thread-safe; speed is fine).

### 5.7 `exporter.py`
`export_csv(report: ScanReport, dest: Path) -> None`. `open(dest, "w", encoding="utf-8-sig", newline="")` with `csv.writer`. Columns: `Rank, File, Path, Match %, Level, Top keywords` (terms joined by `"; "`). Ranked rows only.

### 5.8 GUI (`scanner/gui/app.py`, `worker.py`)
Window: title `config.APP_NAME`, minimum size 900×650, resizable.

Widgets:
- JD: `scrolledtext.ScrolledText`, buttons *Load .txt*, *Clear*.
- Resumes: `ttk.Treeview` or `Listbox` with scrollbar; buttons *Add Files*, *Add Folder*, *Remove*, *Clear all*; label "Resumes (n)".
- Controls: *Scan & Rank*, *Cancel* (disabled when idle), `ttk.Progressbar` + "n / N" label.
- Results: `ttk.Notebook` with tab **Ranking** (Treeview: Rank, File, Match %, Level, Top keywords) and tab **Skipped (n)** (Treeview: File, Reason). Row tags color by level (soft green / light green / amber / grey). Click a column header to sort. Selecting a row shows full path and top terms in a small detail label.
- *Export CSV* button (enabled only when results exist), `filedialog.asksaveasfilename`.
- Status bar (`ttk.Label`, sunken) at the bottom.

Threading protocol (`worker.py`):
```python
@dataclass class Progress:  done: int; total: int; name: str
@dataclass class Finished:  report: ScanReport
@dataclass class Failed:    message: str
@dataclass class Cancelled: pass

class ScanWorker(threading.Thread):
    def __init__(self, jd, paths, out_queue, cancel_event): ...   # daemon=True
    def run(self): ...   # try scan_and_rank; put Progress/Finished; except ScanCancelled -> Cancelled;
                         # except ScannerError -> Failed(str(e)); except Exception -> log + Failed("Unexpected error")
```
GUI side: `_poll_queue()` drains with `get_nowait()` until `queue.Empty`, updates widgets, then `root.after(QUEUE_POLL_MS, self._poll_queue)`. While a scan runs: disable *Scan*, enable *Cancel*, disable add/remove buttons. On window close during a scan: set the cancel event, then destroy. Never call widget methods from the worker.

## 6. Error handling matrix
| Situation | Exception | What the user sees |
|---|---|---|
| Empty JD / only stop words | `InvalidJobDescriptionError` | Message box: "Job description has no meaningful keywords" |
| No resumes added | (GUI check) | Message box: "Add at least one resume" |
| Unsupported extension | `UnsupportedFormatError` | Skipped tab: "Unsupported file type" |
| `.doc`, no LibreOffice | `UnsupportedFormatError` | Skipped tab: ".doc needs LibreOffice, or save as .docx" |
| File over size limit | `FileTooLargeError` | Skipped tab: "File larger than N MB" |
| Corrupt / password PDF | `ExtractionError` | Skipped tab with short reason |
| Scanned PDF / empty file | `EmptyTextError` | Skipped tab: "No readable text (scanned or image-only?)" |
| Cancel clicked | `ScanCancelled` | Status: "Scan cancelled" |
| Anything unexpected | `Exception` (logged) | Skipped row or message box: "Unexpected error. See logs." |

## 7. Testing strategy (pytest)
Build all fixtures in `tmp_path` using python-docx and PyMuPDF. Do not commit binaries.

| File | Cases |
|---|---|
| `test_extractors.py` | txt utf-8 + cp1252; docx body + table text; pdf text; empty pdf → `EmptyTextError`; unsupported ext; oversize file; corrupt file → `ExtractionError`; `.doc` without soffice → `UnsupportedFormatError` (monkeypatch `shutil.which`) |
| `test_preprocess.py` | `c++`/`c#`/`.net`/`node.js` mapped; URL/email/phone removed; numbers removed, `python3` kept; synonyms expanded; idempotent; empty string |
| `test_ranker.py` | relevant resume outranks irrelevant; identical text ≥ 99%; deterministic order; tie → filename; JD of stop words → error; single resume works; level boundaries; top terms contain an expected keyword |
| `test_pipeline.py` | bad file lands in `failures`, others ranked; all files bad → empty `ranked`; cancel raises `ScanCancelled`; progress called N times; duplicate paths collapsed |
| `test_exporter.py` | CSV has BOM, header, correct row count |
| `test_architecture.py` | no `tkinter` import in any `scanner/*.py` outside `gui/` |

GUI: manual checklist in `docs/PROGRESS.md` (window opens, add/remove, scan 20 files without freezing, cancel, export, skipped tab).

## 8. Logging and privacy
Local only. No network calls anywhere. Log levels: INFO for scan start/end and counts, WARNING for skipped files, ERROR/exception for unexpected failures. Never write resume text or JD text to logs. `sample_data/` holds synthetic data only; `.gitignore` excludes `sample_data/resumes/real/` and `logs/`.

## 9. Performance notes
Extraction dominates runtime; TF-IDF on a few hundred documents takes milliseconds. Keep extraction sequential. Soft cap `MAX_RESUMES` (warn above it). Measure and record the real timing in the report.

## 10. Evaluation script (`scripts/evaluate.py`)
Inputs: `--jd <txt>`, `--resumes-dir <dir>`, `--labels <csv: filename,grade 0-3>`.
Output (markdown table printed to console): Spearman ρ and Precision@5 for **system**, **random** (fixed seed) and **keyword-overlap count** baselines. Use `scipy.stats.spearmanr` (SciPy is already installed with scikit-learn). Precision@5 counts grade ≥ 2 as relevant. A `--sweep` flag prints the level distribution for candidate thresholds so you can calibrate `LEVEL_THRESHOLDS`.

## 11. Packaging (optional, P8)
`pip install pyinstaller`, then `pyinstaller --noconfirm --windowed --name ResumeScanner run.py`. Expect a large executable (scikit-learn, SciPy) and possible antivirus false positives. Test the built `.exe` on a second machine before promising it in the report.

## 12. Entry point
`run.py`: `from scanner.gui.app import main` / `if __name__ == "__main__": main()`. `main()` calls `setup_logging()`, builds the `Tk` root, creates `MainWindow`, runs `mainloop()`.

## 13. Conventions for commits
Conventional commits, one per phase: `chore: scaffold`, `feat: extractors`, `feat: ranker`, `feat(gui): wiring`, `docs: readme`.

## 14. `config.py` defaults
```python
APP_NAME = "Resume Scanner & Ranker"
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}
MAX_FILE_MB = 10
MIN_TEXT_CHARS = 50
MIN_JD_CHARS = 20
MAX_RESUMES = 500
TOP_TERMS = 8

# Level thresholds on Match %, checked top to bottom. Starting guesses: calibrate in P7.
LEVEL_THRESHOLDS = ((40.0, "EXCELLENT"), (25.0, "GOOD"), (12.0, "FAIR"))   # else LOW

TFIDF_NGRAM_RANGE = (1, 2)
TFIDF_SUBLINEAR_TF = True

TECH_TOKEN_MAP = {            # regex -> replacement, applied before punctuation stripping
    r"(?<!\w)c\+\+": "cplusplus",
    r"(?<!\w)c#": "csharp",
    r"\.net\b": "dotnet",
    r"node\.js": "nodejs",
    r"scikit-learn": "scikitlearn",
    r"ci/cd": "cicd",
}
SYNONYMS = {                  # whole-word, applied to JD and resumes alike
    "ml": "machine learning",
    "nlp": "natural language processing",
    "js": "javascript",
    "k8s": "kubernetes",
    "ai": "artificial intelligence",
}
EXTRA_STOPWORDS = frozenset({
    "resume", "curriculum", "vitae", "cv", "references", "reference",
    "available", "request", "upon", "email", "phone", "mobile", "address",
    "objective", "summary", "name", "date", "place",
})   # starter list; tune after looking at real output

SOFFICE_CANDIDATES = (
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
)
SOFFICE_TIMEOUT_S = 60
QUEUE_POLL_MS = 100
LOG_DIR = "logs"
LOG_FILE = "resume_scanner.log"
```
