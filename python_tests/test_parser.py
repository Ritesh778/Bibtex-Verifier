import pytest

from bibtex_verifier.parser import (
    BibtexInputError,
    parse,
)


def test_parse_bibliography() -> None:
    bibtex = """
    @article{janga2026,
        title={A Reliable Verifier},
        author={Janga, Ritesh},
        year={2026},
        doi={https://doi.org/10.1000/Test}
    }
    """

    entries, warnings = parse(bibtex)

    assert warnings == []
    assert len(entries) == 1

    entry = entries[0]

    assert entry.citation_key == "janga2026"
    assert entry.entry_type == "article"
    assert entry.title == "A Reliable Verifier"
    assert entry.author == "Janga, Ritesh"
    assert entry.year == "2026"
    assert entry.doi == "https://doi.org/10.1000/Test"


@pytest.mark.parametrize(
    "text",
    [
        ('@string{venue="ACL"}\n@article{x,title={Test},booktitle=venue}'),
        "@article(x,title={Test})",
        "@article{x,title={A} # {B}}",
    ],
)
def test_rejects_unsafe_constructs(
    text: str,
) -> None:
    with pytest.raises(BibtexInputError):
        parse(text)


def test_duplicate_keys_are_reported() -> None:
    bibtex = """
    @article{x,
        title={First Paper}
    }

    @article{x,
        title={Second Paper}
    }
    """

    _, warnings = parse(bibtex)

    assert "Duplicate citation key: x" in warnings


def test_missing_title_is_reported() -> None:
    bibtex = """
    @article{missingtitle,
        author={Janga, Ritesh},
        year={2026}
    }
    """

    _, warnings = parse(bibtex)

    assert "Entry missingtitle has no title." in warnings


def test_entry_limit_is_enforced() -> None:
    bibtex = "\n".join((f"@article{{paper{index},title={{Paper {index}}}}}") for index in range(3))

    with pytest.raises(
        BibtexInputError,
        match="2-entry limit",
    ):
        parse(
            bibtex,
            max_entries=2,
        )
