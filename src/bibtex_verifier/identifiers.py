import re


def normalize_doi(value: str | None) -> str:
    if not value:
        return ""

    doi = value.strip().strip("{}")
    doi = re.sub(r"^doi:\s*", "", doi, flags=re.IGNORECASE)
    doi = re.sub(
        r"^https?://(?:dx\.)?doi\.org/",
        "",
        doi,
        flags=re.IGNORECASE,
    )

    return doi.strip().rstrip(".,;").lower()


def normalize_title(value: str | None) -> str:
    if not value:
        return ""

    value = re.sub(r"\\[a-zA-Z]+\s*", "", value)
    value = value.replace("{", "").replace("}", "")
    value = re.sub(r"[^\w\s]", " ", value.casefold())

    return " ".join(value.split())


def author_surnames(value: str | None) -> set[str]:
    if not value:
        return set()

    surnames = set()

    for raw_name in re.split(r"\s+and\s+", value, flags=re.IGNORECASE):
        name = raw_name.strip()

        if not name:
            continue

        surname = name.split(",", 1)[0] if "," in name else name.split()[-1]

        surnames.add(surname.casefold())

    return surnames


def normalize_pages(value: str | None) -> str:
    if not value:
        return ""

    normalized = value.strip()

    normalized = normalized.replace(
        "\u2013",
        "-",
    )
    normalized = normalized.replace(
        "\u2014",
        "-",
    )

    normalized = re.sub(
        r"\s*-+\s*",
        "-",
        normalized,
    )

    return normalized.casefold()


def format_bibtex_pages(value: str | None) -> str:
    """Format a page range using BibTeX's conventional double hyphen."""
    normalized = normalize_pages(value)

    if not normalized:
        return ""

    return re.sub(r"(?<=\d)-(?=\d)", "--", normalized)
