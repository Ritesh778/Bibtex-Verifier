import httpx
import pytest

from bibtex_verifier.models import (
    Publication,
    Status,
)
from bibtex_verifier.parser import BibtexInputError
from bibtex_verifier.service import (
    VerificationService,
)


class StubProvider:
    def __init__(
        self,
        name: str,
        records: list[Publication],
    ) -> None:
        self.name = name
        self.records = records

    async def find(
        self,
        entry: Publication,
    ) -> list[Publication]:
        return self.records


def create_client() -> httpx.AsyncClient:
    transport = httpx.MockTransport(lambda request: httpx.Response(500))

    return httpx.AsyncClient(transport=transport)


async def test_service_uses_source_consensus() -> None:
    client = create_client()
    service = VerificationService(client=client)

    record = Publication(
        title="A Reliable Citation Verifier",
        author="Janga, Ritesh",
        year="2026",
        doi="10.1000/test",
    )

    service.providers = [
        StubProvider(
            "crossref",
            [record.model_copy(update={"source": "crossref"})],
        ),
        StubProvider(
            "openalex",
            [record.model_copy(update={"source": "openalex"})],
        ),
    ]

    result = await service.verify_entry(
        Publication(
            citation_key="janga2026",
            title=record.title,
            author=record.author,
            year=record.year,
            doi=record.doi,
        )
    )

    await client.aclose()

    assert result.status == Status.VERIFIED
    assert result.confidence is not None
    assert result.confidence >= 98
    assert result.sources == [
        "crossref",
        "openalex",
    ]


async def test_service_reports_doi_conflict() -> None:
    client = create_client()
    service = VerificationService(client=client)

    service.providers = [
        StubProvider(
            "crossref",
            [
                Publication(
                    title="Same Paper",
                    doi="10.1000/wrong",
                    source="crossref",
                )
            ],
        )
    ]

    result = await service.verify_entry(
        Publication(
            citation_key="paper",
            title="Same Paper",
            doi="10.1000/right",
        )
    )

    await client.aclose()

    assert result.status == Status.CONFLICT
    assert result.confidence == 0


async def test_service_reports_unresolved_entry() -> None:
    client = create_client()
    service = VerificationService(client=client)

    service.providers = [
        StubProvider("crossref", []),
        StubProvider("openalex", []),
        StubProvider(
            "semantic_scholar",
            [],
        ),
    ]

    result = await service.verify_entry(
        Publication(
            citation_key="unknown",
            title="An Unknown Research Paper",
        )
    )

    await client.aclose()

    assert result.status == Status.UNRESOLVED
    assert result.matched is None


async def test_service_suggests_metadata_updates() -> None:
    client = create_client()
    service = VerificationService(client=client)

    record = Publication(
        title="A Reliable Citation Verifier",
        author="Janga, Ritesh",
        year="2026",
        journal="Research Systems",
        doi="10.1000/test",
        source="crossref",
    )

    service.providers = [
        StubProvider(
            "crossref",
            [record],
        )
    ]

    result = await service.verify_entry(
        Publication(
            citation_key="janga2026",
            title=record.title,
            author=record.author,
            year=record.year,
            doi=record.doi,
        )
    )

    await client.aclose()

    assert result.status == Status.SUGGESTED_UPDATES

    changed_fields = {difference.field for difference in result.field_differences}

    assert "journal" in changed_fields


async def test_service_rejects_batch_above_configured_limit() -> None:
    client = create_client()
    service = VerificationService(
        client=client,
        max_entries=1,
    )

    bibtex = """
    @article{first,
      title={First Paper},
      year={2025}
    }

    @article{second,
      title={Second Paper},
      year={2026}
    }
    """

    with pytest.raises(
        BibtexInputError,
        match="1-entry limit",
    ):
        await service.verify_bibtex(bibtex)

    await client.aclose()


async def test_published_record_is_preferred_over_preprint() -> None:
    client = create_client()
    service = VerificationService(client=client)

    title = "AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversations"

    published = Publication(
        title=title,
        author="Wu, Qingyun and Bansal, Gagan",
        year="2024",
        booktitle="First Conference on Language Modeling",
        url="https://openreview.net/forum?id=BAakY1hNKs",
        source="openalex",
    )

    preprint = Publication(
        title=title,
        author="Wu, Qingyun and Bansal, Gagan",
        year="2023",
        journal="arXiv",
        url="https://arxiv.org/abs/2308.08155",
        source="semantic_scholar",
    )

    service.providers = [
        StubProvider("semantic_scholar", [preprint]),
        StubProvider("openalex", [published]),
    ]

    result = await service.verify_entry(
        Publication(
            citation_key="wu2024autogen",
            title=title,
            author="Wu, Qingyun and Bansal, Gagan",
            year="2024",
            booktitle="First Conference on Language Modeling",
        )
    )

    await client.aclose()

    assert result.matched is not None
    assert result.matched.year == "2024"
    assert result.matched.booktitle == ("First Conference on Language Modeling")
    assert result.matched.journal == ""
    assert "arxiv.org" not in result.matched.url


async def test_preprint_is_used_when_no_published_record_exists() -> None:
    client = create_client()
    service = VerificationService(client=client)

    preprint = Publication(
        title="A Preprint-Only Research Paper",
        author="Janga, Ritesh",
        year="2026",
        journal="arXiv",
        url="https://arxiv.org/abs/2601.00001",
        source="semantic_scholar",
    )

    service.providers = [
        StubProvider(
            "semantic_scholar",
            [preprint],
        )
    ]

    result = await service.verify_entry(
        Publication(
            citation_key="janga2026preprint",
            title=preprint.title,
            author=preprint.author,
        )
    )

    await client.aclose()

    assert result.matched is not None
    assert result.matched.journal == "arXiv"
    assert result.matched.year == "2026"
    assert result.matched.url == ("https://arxiv.org/abs/2601.00001")
