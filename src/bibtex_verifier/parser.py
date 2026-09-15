from __future__ import annotations

import re

import bibtexparser

from .models import Publication


class BibtexInputError(ValueError):
    """Raised when the submitted BibTeX cannot be safely processed."""


def inspect(text: str) -> list[str]:
    errors = []

    if re.search(
        r"@\w+\s*\(",
        text,
        flags=re.IGNORECASE,
    ):
        errors.append("Parenthesized entries are not accepted; use braces around each entry.")

    if re.search(
        r"@(?:string|preamble)\s*[({]",
        text,
        flags=re.IGNORECASE,
    ):
        errors.append("String macros and preambles are not accepted because export may be lossy.")

    if re.search(
        r'=\s*(?:\{[^}]*\}|"[^"]*"|\w+)\s*#',
        text,
    ):
        errors.append("Concatenated values using # are not accepted because export may be lossy.")

    return errors


def parse(
    text: str,
    *,
    max_entries: int = 5000,
) -> tuple[list[Publication], list[str]]:
    errors = inspect(text)

    if errors:
        raise BibtexInputError(" ".join(errors))

    try:
        database = bibtexparser.loads(text)
    except Exception as exc:
        raise BibtexInputError(f"Could not parse BibTeX: {exc}") from exc

    if len(database.entries) > max_entries:
        raise BibtexInputError(f"Bibliography exceeds the {max_entries}-entry limit.")

    publications = []
    warnings = []
    seen = set()

    for raw in database.entries:
        key = raw.get("ID", "")
        normalized_key = key.casefold()

        if not key:
            warnings.append("An entry has an empty citation key.")
        elif normalized_key in seen:
            warnings.append(f"Duplicate citation key: {key}")

        seen.add(normalized_key)

        if not raw.get("title"):
            warnings.append(f"Entry {key or '(unknown)'} has no title.")

        publication_fields = {
            field: str(raw.get(field, "")) for field in Publication.model_fields if field in raw
        }

        publications.append(
            Publication(
                citation_key=key,
                entry_type=raw.get(
                    "ENTRYTYPE",
                    "misc",
                ),
                **publication_fields,
            )
        )

    unique_warnings = list(dict.fromkeys(warnings))

    return publications, unique_warnings
