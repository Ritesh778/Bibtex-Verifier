from bibtex_verifier.identifiers import (
    author_surnames,
    format_bibtex_pages,
    normalize_doi,
    normalize_pages,
    normalize_title,
)


def test_normalize_doi_removes_url_and_punctuation():
    value = "https://doi.org/10.1000/Test-DOI."

    assert normalize_doi(value) == "10.1000/test-doi"


def test_normalize_doi_handles_bibtex_braces():
    value = "{doi:10.5555/Example}"

    assert normalize_doi(value) == "10.5555/example"


def test_normalize_title_ignores_case_and_braces():
    value = "{Evidence}-Based BibTeX Verification"

    assert normalize_title(value) == "evidence based bibtex verification"


def test_author_surnames_supports_bibtex_names():
    value = "Janga, Ritesh and Yagna Manasa Boyapati"

    assert author_surnames(value) == {
        "janga",
        "boyapati",
    }


def test_normalize_pages_handles_bibtex_ranges():
    assert normalize_pages("436--444") == "436-444"
    assert normalize_pages("436-444") == "436-444"
    assert normalize_pages("436 – 444") == "436-444"
    assert normalize_pages("436—444") == "436-444"


def test_format_bibtex_pages_formats_range() -> None:
    assert format_bibtex_pages("4171-4186") == "4171--4186"
    assert format_bibtex_pages("4171--4186") == "4171--4186"
    assert format_bibtex_pages("4171–4186") == "4171--4186"


def test_format_bibtex_pages_preserves_single_page() -> None:
    assert format_bibtex_pages("4171") == "4171"
    assert format_bibtex_pages("") == ""
