from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from urllib.parse import quote

import httpx

from .identifiers import (
    format_bibtex_pages,
    normalize_doi,
)
from .models import Publication


class ProviderError(RuntimeError):
    """Raised when an external research provider cannot be queried."""


class Provider(ABC):
    name: str

    def __init__(
        self,
        client: httpx.AsyncClient,
        api_key: str = "",
        email: str = "",
    ) -> None:
        self.client = client
        self.api_key = api_key
        self.email = email

    async def get_json(
        self,
        url: str,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict | None:
        for attempt in range(3):
            try:
                response = await self.client.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=15,
                )

                if response.status_code == 404:
                    return None

                if response.status_code == 429 or response.status_code >= 500:
                    if attempt == 2:
                        raise ProviderError(f"{self.name} returned HTTP {response.status_code}")

                    retry_after = response.headers.get("Retry-After")

                    delay = (
                        float(retry_after)
                        if retry_after and retry_after.isdigit()
                        else 1.5 * 2**attempt
                    )

                    await asyncio.sleep(min(delay, 15))
                    continue

                response.raise_for_status()
                return response.json()

            except (
                httpx.TimeoutException,
                httpx.NetworkError,
            ) as exc:
                if attempt == 2:
                    raise ProviderError(f"{self.name} is unavailable") from exc

                await asyncio.sleep(1.5 * 2**attempt)

        return None

    @abstractmethod
    async def find(
        self,
        entry: Publication,
    ) -> list[Publication]:
        """Find publications that may match the entry."""


class CrossrefProvider(Provider):
    name = "crossref"
    base_url = "https://api.crossref.org/works"

    async def find(
        self,
        entry: Publication,
    ) -> list[Publication]:
        doi = normalize_doi(entry.doi)

        contact = {"mailto": self.email} if self.email else {}

        if doi:
            data = await self.get_json(
                f"{self.base_url}/{quote(doi, safe='')}",
                contact,
            )

            return [self.convert(data["message"])] if data and data.get("message") else []

        data = await self.get_json(
            self.base_url,
            {
                "query.title": entry.title,
                "rows": "5",
                **contact,
            },
        )

        items = (data or {}).get("message", {}).get("items", [])

        return [self.convert(item) for item in items]

    def convert(
        self,
        item: dict,
    ) -> Publication:
        authors = []

        for author in item.get("author", []):
            family = author.get("family", "")
            given = author.get("given", "")

            authors.append(f"{family}, {given}".strip(", "))

        date = item.get("published-print") or item.get("published-online") or {}

        date_parts = date.get(
            "date-parts",
            [[]],
        )

        return Publication(
            title=(item.get("title") or [""])[0],
            author=" and ".join(filter(None, authors)),
            year=(str(date_parts[0][0]) if date_parts and date_parts[0] else ""),
            journal=(item.get("container-title") or [""])[0],
            volume=item.get("volume", ""),
            number=item.get("issue", ""),
            pages=format_bibtex_pages(item.get("page", "")),
            doi=item.get("DOI", ""),
            publisher=item.get(
                "publisher",
                "",
            ),
            url=item.get("URL", ""),
            source=self.name,
        )


class OpenAlexProvider(Provider):
    name = "openalex"
    base_url = "https://api.openalex.org/works"

    async def find(
        self,
        entry: Publication,
    ) -> list[Publication]:
        doi = normalize_doi(entry.doi)

        params = {
            "per_page": "5",
        }

        if self.api_key:
            params["api_key"] = self.api_key

        if doi:
            params["filter"] = f"doi:https://doi.org/{doi}"
        else:
            params["search"] = entry.title

        data = await self.get_json(
            self.base_url,
            params,
        )

        return [
            self.convert(item)
            for item in (data or {}).get(
                "results",
                [],
            )
        ]

    def convert(
        self,
        item: dict,
    ) -> Publication:
        authors = [
            authorship.get("author", {}).get("display_name", "")
            for authorship in item.get(
                "authorships",
                [],
            )
        ]

        location = item.get("primary_location") or {}
        source = location.get("source") or {}
        bibliography = item.get("biblio") or {}

        first_page = bibliography.get("first_page") or ""
        last_page = bibliography.get("last_page") or ""

        pages = format_bibtex_pages(
            f"{first_page}-{last_page}" if first_page and last_page else first_page
        )

        return Publication(
            title=(
                item.get("title")
                or item.get(
                    "display_name",
                    "",
                )
            ),
            author=" and ".join(filter(None, authors)),
            year=str(item.get("publication_year") or ""),
            journal=source.get(
                "display_name",
                "",
            ),
            volume=bibliography.get("volume") or "",
            number=bibliography.get("issue") or "",
            pages=pages,
            doi=normalize_doi(item.get("doi", "")),
            publisher=source.get(
                "host_organization_name",
                "",
            ),
            url=item.get("id", ""),
            source=self.name,
        )


class SemanticScholarProvider(Provider):
    name = "semantic_scholar"
    base_url = "https://api.semanticscholar.org/graph/v1/paper"
    fields = "title,authors,year,venue,publicationVenue,externalIds,url"

    async def find(
        self,
        entry: Publication,
    ) -> list[Publication]:
        doi = normalize_doi(entry.doi)

        headers = {"x-api-key": self.api_key} if self.api_key else None

        if doi:
            data = await self.get_json(
                f"{self.base_url}/DOI:{quote(doi, safe='')}",
                {"fields": self.fields},
                headers,
            )

            return [self.convert(data)] if data else []

        data = await self.get_json(
            f"{self.base_url}/search",
            {
                "query": entry.title,
                "limit": "5",
                "fields": self.fields,
            },
            headers,
        )

        return [
            self.convert(item)
            for item in (data or {}).get(
                "data",
                [],
            )
        ]

    def convert(
        self,
        item: dict,
    ) -> Publication:
        publication_venue = item.get("publicationVenue") or {}

        venue = publication_venue.get("name") or item.get("venue", "")

        external_ids = item.get("externalIds") or {}

        authors = [
            author.get("name", "")
            for author in item.get(
                "authors",
                [],
            )
        ]

        return Publication(
            title=item.get("title", ""),
            author=" and ".join(filter(None, authors)),
            year=str(item.get("year") or ""),
            journal=venue,
            doi=external_ids.get(
                "DOI",
                "",
            ),
            url=item.get("url", ""),
            source=self.name,
        )
