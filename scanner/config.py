"""Project-wide constants for Resume Scanner & Ranker.

All thresholds, limits, stop words and token maps live here. No magic
numbers elsewhere in the codebase.
"""


APP_NAME = "Resume Scanner & Ranker"

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}
MAX_FILE_MB = 10
MIN_TEXT_CHARS = 50
MIN_JD_CHARS = 20
MAX_RESUMES = 500
TOP_TERMS = 8

# Level thresholds on Match %, checked top to bottom. Starting guesses:
# calibrate in P7. Else LOW.
LEVEL_THRESHOLDS = ((40.0, "EXCELLENT"), (25.0, "GOOD"), (12.0, "FAIR"))

TFIDF_NGRAM_RANGE = (1, 2)
TFIDF_SUBLINEAR_TF = True

TECH_TOKEN_MAP = {
    r"(?<!\w)c\+\+": "cplusplus",
    r"(?<!\w)c#": "csharp",
    r"\.net\b": "dotnet",
    r"node\.js": "nodejs",
    r"scikit-learn": "scikitlearn",
    r"ci/cd": "cicd",
}

SYNONYMS = {
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
})

SOFFICE_CANDIDATES = (
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
)
SOFFICE_TIMEOUT_S = 60
QUEUE_POLL_MS = 100

LOG_DIR = "logs"
LOG_FILE = "resume_scanner.log"
