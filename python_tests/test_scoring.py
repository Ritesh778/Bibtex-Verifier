from bibtex_verifier.models import Publication
from bibtex_verifier.scoring import (
    assess,
    author_similarity,
    same_work,
    similarity,
)


def test_equivalent_titles_match() -> None:
    score = similarity(
        "Evidence-Based Citation Verification",
        "Citation Verification: Evidence Based",
    )

    assert score == 100.0


def test_author_similarity_uses_surnames() -> None:
    score = author_similarity(
        "Janga, Ritesh and Boyapati, Yagna",
        "Ritesh Janga and Yagna Boyapati",
    )

    assert score == 100.0


def test_exact_doi_is_high_confidence() -> None:
    original = Publication(
        title="Working title",
        doi="https://doi.org/10.1/ABC",
    )

    candidate = Publication(
        title="Published title",
        doi="10.1/abc",
    )

    evidence = assess(
        original,
        candidate,
    )

    assert evidence.confidence >= 98
    assert evidence.decision == "high"
    assert evidence.signals["doi"] == "exact"


def test_conflicting_dois_are_rejected() -> None:
    original = Publication(
        title="Same title",
        doi="10.1/a",
    )

    candidate = Publication(
        title="Same title",
        doi="10.1/b",
    )

    evidence = assess(
        original,
        candidate,
    )

    assert evidence.decision == "conflict"
    assert evidence.confidence == 0
    assert not same_work(
        original,
        candidate,
    )


def test_independent_sources_increase_confidence() -> None:
    original = Publication(title=("Evidence Based Citation Verification"))

    candidate = Publication(title=("Evidence-Based Citation Verification"))

    one_source = assess(
        original,
        candidate,
        source_count=1,
    )

    three_sources = assess(
        original,
        candidate,
        source_count=3,
    )

    assert three_sources.confidence > one_source.confidence


def test_different_years_are_not_same_work() -> None:
    first = Publication(
        title="A Reliable Citation Verifier",
        author="Janga, Ritesh",
        year="2020",
    )

    second = Publication(
        title="A Reliable Citation Verifier",
        author="Janga, Ritesh",
        year="2026",
    )

    assert not same_work(first, second)
