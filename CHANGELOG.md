# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] - 2026-09-13

### Added

- DOI normalization and DOI-first lookups across Crossref, Semantic Scholar, and OpenAlex.
- Source-order-independent consensus matching across the three indexes.
- In-memory lookup caching for repeated entries.
- Explainable confidence assessments using identifier, title, author, year, and source evidence.
- Downloadable JSON evidence reports with a SHA-256 input fingerprint for reproducibility.
- Request timeouts and support for API `Retry-After` guidance.
- Safe input limits and preflight detection of unsupported, potentially lossy BibTeX constructs.
- Tests covering identifier normalization, DOI conflicts, and evidence-based selection.

### Changed

- Renamed potentially misleading result labels: “Auto-Updated” is now “Suggested Updates,” and “Not Found” is now “Unresolved.”
- Clarified that an unresolved lookup is not proof that a citation was fabricated.
- Added Subresource Integrity validation for the browser fuzzy-matching dependency.
