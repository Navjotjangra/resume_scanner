"""Text preprocessing for Resume Scanner & Ranker.

Implements ``normalize_text`` following the 7-step pipeline in TRD §5.4,
in that exact order. All token maps and stop-word settings come from
``scanner.config``. Regexes are pre-compiled at module level.

The function is idempotent: ``normalize_text(normalize_text(x)) ==
normalize_text(x)``.
"""

from __future__ import annotations

import re
import unicodedata

from scanner.config import SYNONYMS, TECH_TOKEN_MAP

# Step 2 patterns (applied after NFKC + lower-case).
URL_RE = re.compile(r"https?://\S+|www\.\S+")
EMAIL_RE = re.compile(r"[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}")
PHONE_RE = re.compile(r"\+?\d[\d\s().\-]{8,}\d")

# Step 3: tech-token map, regex -> replacement (applied before punctuation
# stripping so tokens like c++ and .net still contain their symbols).
TECH_REPLACEMENTS = [
    (re.compile(pattern), repl) for pattern, repl in TECH_TOKEN_MAP.items()
]

# Step 4: keep only a-z, 0-9 and whitespace; everything else -> space.
NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]")

# Step 5: synonyms as whole-word replacements.
SYNONYM_REPLACEMENTS = [
    (re.compile(r"\b" + re.escape(word) + r"\b"), repl)
    for word, repl in SYNONYMS.items()
]

# Step 6: remove standalone numbers; keep tokens like python3 (no boundary
# between a letter and a digit).
STANDALONE_NUMBER_RE = re.compile(r"\b\d+\b")

# Step 7: collapse whitespace.
WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Clean and normalize resume/JD text.

    Steps, in order:
    1. NFKC normalize + lower-case.
    2. Remove URLs, emails and phone-like numbers.
    3. Apply TECH_TOKEN_MAP (c++ -> cplusplus, .net -> dotnet, ...).
    4. Replace every char that is not a-z, 0-9 or whitespace with a space.
    5. Apply SYNONYMS as whole-word replacements (ml -> machine learning).
    6. Remove standalone numbers (keeps tokens like python3).
    7. Collapse whitespace and strip.
    """
    # Step 1.
    text = unicodedata.normalize("NFKC", text).lower()

    # Step 2.
    text = URL_RE.sub(" ", text)
    text = EMAIL_RE.sub(" ", text)
    text = PHONE_RE.sub(" ", text)

    # Step 3.
    for pattern, repl in TECH_REPLACEMENTS:
        text = pattern.sub(repl, text)

    # Step 4.
    text = NON_ALNUM_RE.sub(" ", text)

    # Step 5.
    for pattern, repl in SYNONYM_REPLACEMENTS:
        text = pattern.sub(repl, text)

    # Step 6.
    text = STANDALONE_NUMBER_RE.sub(" ", text)

    # Step 7.
    text = WHITESPACE_RE.sub(" ", text).strip()
    return text
