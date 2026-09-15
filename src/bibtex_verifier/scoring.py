from difflib import SequenceMatcher

from .identifiers import author_surnames, normalize_doi, normalize_title
from .models import Evidence, Publication


def similarity(left: str, right: str) -> float:
    left_tokens = sorted(normalize_title(left).split())
    right_tokens = sorted(normalize_title(right).split())

    return round(
        SequenceMatcher(
            None,
            " ".join(left_tokens),
            " ".join(right_tokens),
        ).ratio()
        * 100,
        1,
    )


def author_similarity(left: str, right: str) -> float:
    left_surnames = author_surnames(left)
    right_surnames = author_surnames(right)

    if not left_surnames and not right_surnames:
        return 100.0

    if not left_surnames or not right_surnames:
        return 0.0

    matching_authors = len(left_surnames & right_surnames)
    largest_author_count = max(
        len(left_surnames),
        len(right_surnames),
    )

    return round(
        matching_authors / largest_author_count * 100,
        1,
    )


def assess(
    original: Publication,
    candidate: Publication,
    source_count: int = 1,
) -> Evidence:
    original_doi = normalize_doi(original.doi)
    candidate_doi = normalize_doi(candidate.doi)

    title_score = similarity(
        original.title,
        candidate.title,
    )
    author_score = author_similarity(
        original.author,
        candidate.author,
    )

    year_agrees = bool(original.year and candidate.year and original.year == candidate.year)

    signals: dict[str, str | int | float | None] = {
        "doi": "unavailable",
        "title": title_score,
        "authors": author_score,
        "year": (100 if year_agrees else 0 if original.year and candidate.year else None),
        "sources": source_count,
    }

    if original_doi and candidate_doi and original_doi != candidate_doi:
        signals["doi"] = "conflict"

        return Evidence(
            confidence=0,
            decision="conflict",
            reasons=["DOI conflicts with the matched database record"],
            signals=signals,
        )

    if (
        original_doi
        and candidate_doi
        and original_doi == candidate_doi
        and original.title
        and candidate.title
        and title_score < 60
    ):
        signals["doi"] = "exact"

        return Evidence(
            confidence=0,
            decision="conflict",
            reasons=["DOI resolves to a publication with a substantially different title"],
            signals=signals,
        )

    confidence = title_score * 0.60
    reasons = [f"Title similarity {round(title_score)}%"]

    if original.author and candidate.author:
        confidence += author_score * 0.20
        reasons.append(f"Author agreement {round(author_score)}%")

    if original.year and candidate.year:
        confidence += (100 if year_agrees else 0) * 0.10

        reasons.append("Year agrees" if year_agrees else "Year differs")

    confidence += min(
        max(source_count - 1, 0) * 5,
        10,
    )

    if source_count > 1:
        reasons.append(f"{source_count} independent sources agree")

    if original_doi and candidate_doi and original_doi == candidate_doi:
        confidence = max(
            confidence,
            98,
        )
        signals["doi"] = "exact"
        reasons.insert(
            0,
            "Exact DOI match",
        )

    final_score = round(
        min(
            100,
            confidence,
        )
    )

    if final_score >= 90:
        decision = "high"
    elif final_score >= 75:
        decision = "medium"
    else:
        decision = "low"

    return Evidence(
        confidence=final_score,
        decision=decision,
        reasons=reasons,
        signals=signals,
    )


def same_work(
    left: Publication,
    right: Publication,
) -> bool:
    left_doi = normalize_doi(left.doi)
    right_doi = normalize_doi(right.doi)

    if left_doi and right_doi:
        return left_doi == right_doi

    if similarity(left.title, right.title) < 85:
        return False

    if (
        left.year
        and right.year
        and left.year.isdigit()
        and right.year.isdigit()
        and abs(int(left.year) - int(right.year)) > 1
    ):
        return False

    return not (
        left.author
        and right.author
        and author_similarity(
            left.author,
            right.author,
        )
        < 30
    )
