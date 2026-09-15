# Security Policy

## Reporting a vulnerability

Please do not disclose security vulnerabilities through a public GitHub issue.

Report vulnerabilities privately to the repository maintainer and include:

- A description of the vulnerability
- Steps required to reproduce it
- The affected component or endpoint
- The possible impact
- Any suggested mitigation

Please allow reasonable time for investigation before publicly disclosing the issue.

## Sensitive information

Do not submit bibliographies containing confidential, unpublished, restricted, or personally identifiable information to a shared deployment unless the deployment is approved for that data.

The local command-line tool is recommended when a bibliography should remain on the researcher's computer.

## API credentials

API keys and contact email addresses must be stored in the local `.env` file or deployment secrets.

Never commit:

- `.env`
- API keys
- Access tokens
- Private bibliography files
- Generated reports containing sensitive metadata

The `.env.example` file must contain placeholders only.

## External services

Verification may send publication titles, DOI values, author names, and other citation metadata to external scholarly services, including:

- Crossref
- OpenAlex
- Semantic Scholar

These services may log requests according to their own privacy and retention policies.

## Supported versions

Security fixes are provided for the latest released version of BibTeX Verifier.