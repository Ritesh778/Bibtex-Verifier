from __future__ import annotations

import asyncio
import hashlib
import os
from collections import Counter
from datetime import UTC, datetime

import httpx
from cachetools import TTLCache
from dotenv import load_dotenv

from . import __version__
from .identifiers import (
    normalize_doi,
    normalize_pages,
    normalize_title,
)
from .models import (
    FieldDifference,
    Publication,
    Status,
    VerificationReport,
    VerificationResult,
)
from .parser import parse
from .providers import (
    CrossrefProvider,
    OpenAlexProvider,
    Provider,
    ProviderError,
    SemanticScholarProvider,
)
from .scoring import (
    assess,
    author_similarity,
    same_work,
    similarity,
)

FIELDS = (
    "title",
    "author",
    "year",
    "journal",
    "booktitle",
    "volume",
    "number",
    "pages",
    "doi",
    "publisher",
)

MERGE_FIELDS = FIELDS + ("url",)
PUBLISHED_FIELDS = (
    "year",
    "journal",
    "booktitle",
    "volume",
    "number",
    "pages",
    "publisher",
    "doi",
    "url",
)


def is_preprint(record: Publication) -> bool:
    """Return whether a record represents a repository preprint."""

    journal = record.journal.strip().casefold()
    booktitle = record.booktitle.strip().casefold()
    venue = f"{journal} {booktitle}"
    url = record.url.strip().casefold()
    doi = normalize_doi(record.doi).casefold()

    return (
        "arxiv" in venue
        or journal == "corr"
        or booktitle == "corr"
        or "computing research repository" in venue
        or "biorxiv" in venue
        or "medrxiv" in venue
        or "arxiv.org" in url
        or "biorxiv.org" in url
        or "medrxiv.org" in url
        or doi.startswith("10.48550/arxiv")
    )


def metadata_completeness(
    record: Publication,
) -> int:
    """Count useful metadata fields in a publication record."""

    return sum(
        bool(
            str(
                getattr(
                    record,
                    field,
                    "",
                )
            ).strip()
        )
        for field in MERGE_FIELDS
    )


def same_publication_family(
    left: Publication,
    right: Publication,
) -> bool:
    """Determine whether records are versions of the same work."""

    if same_work(
        left,
        right,
    ):
        return True

    # A published version and a preprint can have different DOIs.
    if not (is_preprint(left) or is_preprint(right)):
        return False

    if (
        not left.title
        or not right.title
        or similarity(
            left.title,
            right.title,
        )
        < 85
    ):
        return False

    if (
        left.year
        and right.year
        and left.year.isdigit()
        and right.year.isdigit()
        and abs(int(left.year) - int(right.year)) > 3
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


class VerificationService:
    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        *,
        max_entries: int | None = None,
    ) -> None:
        load_dotenv()

        if max_entries is None:
            configured_limit = os.getenv(
                "BIBTEX_MAX_ENTRIES",
                "500",
            )

            try:
                max_entries = int(configured_limit)
            except ValueError as exc:
                raise ValueError(
                    "BIBTEX_MAX_ENTRIES must be an integer.",
                ) from exc

        if max_entries < 1:
            raise ValueError(
                "BIBTEX_MAX_ENTRIES must be at least 1.",
            )

        self.max_entries = max_entries

        self.client = client or httpx.AsyncClient(
            headers={"User-Agent": (f"bibtex-verifier/{__version__}")},
            follow_redirects=True,
        )

        self._owns_client = client is None

        self.providers: list[Provider] = [
            CrossrefProvider(
                self.client,
                email=os.getenv(
                    "CROSSREF_MAILTO",
                    "",
                ),
            ),
            OpenAlexProvider(
                self.client,
                api_key=os.getenv(
                    "OPENALEX_API_KEY",
                    "",
                ),
            ),
            SemanticScholarProvider(
                self.client,
                api_key=os.getenv(
                    "SEMANTIC_SCHOLAR_API_KEY",
                    "",
                ),
            ),
        ]

        self.cache: TTLCache[
            str,
            VerificationResult,
        ] = TTLCache(
            maxsize=10_000,
            ttl=86_400,
        )

        self._semaphore = asyncio.Semaphore(8)

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def verify_bibtex(
        self,
        text: str,
    ) -> VerificationReport:
        entries, warnings = parse(
            text,
            max_entries=self.max_entries,
        )

        results = await asyncio.gather(*(self.verify_entry(entry) for entry in entries))

        summary = dict(Counter(result.status.value for result in results))

        return VerificationReport(
            tool_version=__version__,
            generated_at=datetime.now(UTC).isoformat(),
            input_sha256=hashlib.sha256(text.encode()).hexdigest(),
            summary=summary,
            warnings=warnings,
            entries=list(results),
        )

    async def verify_entry(
        self,
        entry: Publication,
    ) -> VerificationResult:
        key = normalize_doi(entry.doi) or normalize_title(entry.title)

        if key in self.cache:
            cached = self.cache[key].model_copy(deep=True)
            cached.citation_key = entry.citation_key
            return cached

        if not entry.title and not entry.doi:
            return VerificationResult(
                citation_key=entry.citation_key,
                title=entry.title,
                status=Status.UNRESOLVED,
            )

        async with self._semaphore:
            responses = await asyncio.gather(
                *(provider.find(entry) for provider in self.providers),
                return_exceptions=True,
            )

        candidates: list[Publication] = []
        failed_sources = []

        for provider, response in zip(
            self.providers,
            responses,
            strict=True,
        ):
            if isinstance(
                response,
                (ProviderError, Exception),
            ):
                failed_sources.append(provider.name)
            else:
                candidates.extend(response)

        clusters = self._cluster(candidates)

        all_ranked = [
            (
                assess(
                    entry,
                    record,
                    len(sources),
                ),
                record,
                sources,
            )
            for record, sources in clusters
        ]

        ranked = [row for row in all_ranked if row[0].decision != "conflict"]

        # A strong published match must take precedence
        # over an arXiv or repository version.
        strong_published = [
            row
            for row in ranked
            if (
                not is_preprint(row[1])
                and row[0].confidence >= 60
                and (
                    not entry.title
                    or similarity(
                        entry.title,
                        row[1].title,
                    )
                    >= 85
                )
            )
        ]

        selection_pool = strong_published or ranked

        winner = max(
            selection_pool,
            key=lambda row: (
                row[0].confidence,
                metadata_completeness(row[1]),
            ),
            default=None,
        )

        only_conflicts = bool(all_ranked) and all(
            row[0].decision == "conflict" for row in all_ranked
        )

        if not winner and only_conflicts:
            evidence, matched, sources = all_ranked[0]

            result = VerificationResult(
                citation_key=entry.citation_key,
                title=entry.title,
                status=Status.CONFLICT,
                confidence=0,
                evidence=evidence,
                sources=sorted(sources),
                matched=matched,
                field_differences=(
                    self._differences(
                        entry,
                        matched,
                    )
                ),
            )

            self.cache[key] = result
            return result

        if not winner or winner[0].confidence < 60:
            result = VerificationResult(
                citation_key=entry.citation_key,
                title=entry.title,
                status=Status.UNRESOLVED,
                sources=[],
            )

            if failed_sources:
                result.evidence = assess(
                    entry,
                    Publication(title=""),
                )

                result.evidence.reasons = ["Unavailable sources: " + ", ".join(failed_sources)]

            self.cache[key] = result
            return result

        evidence, matched, sources = winner

        matched, protected_published = self._protect_published_original(
            entry,
            matched,
        )

        differences = self._differences(
            entry,
            matched,
        )

        status = Status.VERIFIED if not differences else Status.SUGGESTED_UPDATES

        if evidence.decision == "low" or protected_published:
            status = Status.NEEDS_REVIEW

        if protected_published:
            evidence.reasons.insert(
                0,
                (
                    "An older or preprint record was found; "
                    "the existing published metadata was preserved"
                ),
            )

        original_is_published = bool(
            entry.journal.strip() or entry.booktitle.strip()
        ) and not is_preprint(entry)

        # Never automatically downgrade an existing
        # conference or journal citation to a preprint.
        if original_is_published and is_preprint(matched):
            status = Status.NEEDS_REVIEW

            evidence.reasons.insert(
                0,
                (
                    "Only a preprint record was found; "
                    "the existing published metadata "
                    "was preserved for manual review"
                ),
            )

        result = VerificationResult(
            citation_key=entry.citation_key,
            title=entry.title,
            status=status,
            confidence=evidence.confidence,
            evidence=evidence,
            sources=sorted(sources),
            matched=matched,
            field_differences=differences,
        )

        self.cache[key] = result
        return result

    @staticmethod
    def _protect_published_original(
        original: Publication,
        matched: Publication,
    ) -> tuple[Publication, bool]:
        original_is_published = bool(
            original.journal.strip() or original.booktitle.strip()
        ) and not is_preprint(original)

        original_year = int(original.year) if original.year.isdigit() else None
        matched_year = int(matched.year) if matched.year.isdigit() else None

        older_match = (
            original_year is not None and matched_year is not None and matched_year < original_year
        )

        publication_needs_protection = original_is_published and (
            is_preprint(matched) or older_match
        )

        original_authors = [
            author.strip() for author in original.author.split(" and ") if author.strip()
        ]

        matched_authors = [
            author.strip() for author in matched.author.split(" and ") if author.strip()
        ]

        matched_is_truncated = "others" in matched.author.casefold()

        author_needs_protection = bool(original.author) and (
            matched_is_truncated
            or (matched.author and len(original_authors) > len(matched_authors))
        )

        if not (publication_needs_protection or author_needs_protection):
            return matched, False

        protected = matched.model_copy(deep=True)

        if publication_needs_protection:
            for field in PUBLISHED_FIELDS:
                original_value = getattr(original, field)

                if original_value:
                    setattr(
                        protected,
                        field,
                        original_value,
                    )

        if author_needs_protection:
            protected.author = original.author

        return protected, True

    @staticmethod
    def _cluster(
        candidates: list[Publication],
    ) -> list[
        tuple[
            Publication,
            set[str],
        ]
    ]:
        groups: list[list[Publication]] = []

        for candidate in candidates:
            group = next(
                (
                    existing
                    for existing in groups
                    if any(
                        same_publication_family(
                            record,
                            candidate,
                        )
                        for record in existing
                    )
                ),
                None,
            )

            if group is None:
                groups.append([candidate])
            else:
                group.append(candidate)

        clusters: list[
            tuple[
                Publication,
                set[str],
            ]
        ] = []

        for group in groups:
            published = [record for record in group if not is_preprint(record)]

            # If a published version exists, preprints
            # are completely excluded from metadata
            # selection and merging.
            eligible = published if published else group

            primary_source = max(
                eligible,
                key=metadata_completeness,
            )

            primary = primary_source.model_copy(deep=True)

            for secondary in eligible:
                if secondary is primary_source:
                    continue

                for field in MERGE_FIELDS:
                    current = getattr(
                        primary,
                        field,
                    )
                    suggested = getattr(
                        secondary,
                        field,
                    )

                    if not current and suggested:
                        setattr(
                            primary,
                            field,
                            suggested,
                        )

            sources = {record.source for record in group if record.source}

            clusters.append(
                (
                    primary,
                    sources,
                )
            )

        return clusters

    @staticmethod
    def _differences(
        original: Publication,
        matched: Publication,
    ) -> list[FieldDifference]:
        differences = []

        for field in FIELDS:
            current = getattr(
                original,
                field,
            )
            suggested = getattr(
                matched,
                field,
            )

            if field == "doi":
                equal = normalize_doi(current) == normalize_doi(suggested)
                score = 100 if equal else 0

            elif field == "author":
                score = author_similarity(
                    current,
                    suggested,
                )
                equal = score == 100

            elif field == "title":
                score = similarity(
                    current,
                    suggested,
                )
                equal = score == 100

            elif field == "pages":
                equal = normalize_pages(current) == normalize_pages(suggested)
                score = 100 if equal else 0

            else:
                equal = current.strip().casefold() == suggested.strip().casefold()
                score = 100 if equal else 0

            if suggested and not equal:
                differences.append(
                    FieldDifference(
                        field=field,
                        original=current,
                        suggested=suggested,
                        score=score,
                        source=matched.source,
                    )
                )

        return differences
