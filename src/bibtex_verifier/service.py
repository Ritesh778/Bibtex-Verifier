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

        winner = max(
            ranked,
            key=lambda row: row[0].confidence,
            default=None,
        )

        only_conflicts = all_ranked and all(row[0].decision == "conflict" for row in all_ranked)

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

        differences = self._differences(
            entry,
            matched,
        )

        status = Status.VERIFIED if not differences else Status.SUGGESTED_UPDATES

        if evidence.decision == "low":
            status = Status.NEEDS_REVIEW

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
    def _cluster(
        candidates: list[Publication],
    ) -> list[tuple[Publication, set[str]]]:
        clusters: list[tuple[Publication, set[str]]] = []

        for candidate in candidates:
            existing = next(
                (
                    item
                    for item in clusters
                    if same_work(
                        item[0],
                        candidate,
                    )
                ),
                None,
            )

            if existing is None:
                clusters.append(
                    (
                        candidate.model_copy(),
                        {candidate.source},
                    )
                )
                continue

            record, sources = existing
            sources.add(candidate.source)

            for field in FIELDS:
                if not getattr(record, field) and getattr(
                    candidate,
                    field,
                ):
                    setattr(
                        record,
                        field,
                        getattr(
                            candidate,
                            field,
                        ),
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
