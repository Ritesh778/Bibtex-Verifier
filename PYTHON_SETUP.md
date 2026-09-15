# BibTeX Verifier Setup

BibTeX Verifier checks bibliography entries against multiple scholarly metadata sources. It includes a browser interface, Python API, and command-line interface.

The verifier uses evidence from Crossref, OpenAlex, and Semantic Scholar. API results can still be incomplete or conflicting, so entries marked **Needs Review** should always be checked manually.

## Requirements

- Python 3.11 or newer
- Git
- Internet access for scholarly metadata lookups
- Docker is optional

## Windows installation

Open PowerShell in the repository directory.

### 1. Create a virtual environment

```powershell
py -m venv .venv
```

### 2. Activate it

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell prevents activation, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 3. Install the project

```powershell
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

### 4. Create the environment file

```powershell
Copy-Item .env.example .env
```

Open `.env` and provide the available configuration values:

```dotenv
CROSSREF_MAILTO=your-university-email@example.edu
OPENALEX_API_KEY=
SEMANTIC_SCHOLAR_API_KEY=
BIBTEX_MAX_ENTRIES=500
CORS_ORIGINS=http://127.0.0.1:8000,http://localhost:8000
```

Crossref and OpenAlex can generally be used without paid API access. A Semantic Scholar API key is recommended but optional.

Never commit `.env` or expose API keys in screenshots, logs, or GitHub.

## Run the application

From the repository root, with the virtual environment activated, run:

```powershell
uvicorn bibtex_verifier.api:app --reload
```

Open the application:

```text
http://127.0.0.1:8000
```

Additional endpoints:

- API documentation: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`
- OpenAPI schema: `http://127.0.0.1:8000/openapi.json`

Stop the server by pressing `Ctrl+C`.

## Verify a reference in the browser

Paste a BibTeX entry into the **Paste BibTeX** tab and select **Verify pasted BibTeX**.

Example:

```bibtex
@inproceedings{devlin2019bert,
  title={BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding},
  author={Devlin, Jacob and Chang, Ming-Wei and Lee, Kenton and Toutanova, Kristina},
  booktitle={Proceedings of NAACL-HLT},
  year={2019},
  doi={10.18653/v1/N19-1423}
}
```

The verifier may recommend the complete conference name, page range, and publisher. Review proposed changes before accepting them.

## Command-line usage

Verify a BibTeX file:

```powershell
bibtex-verify .\test_refs.bib
```

Write the JSON report to a specific file:

```powershell
bibtex-verify .\test_refs.bib --output .\verification-report.json
```

View all CLI options:

```powershell
bibtex-verify --help
```

## Development checks

Run these checks before committing changes:

```powershell
ruff format --check src python_tests
ruff check src python_tests
pytest -q
node --check docs/app.js
node --check docs/backend-api.js
node .\tests\test_lib.js
git diff --check
```

The JavaScript tests may report that `fuzzball` is unavailable if npm dependencies have not been installed. The fallback matcher is used in that case.

## Optional Docker setup

Docker is not required for local use.

After installing Docker Desktop, build the image from the repository root:

```powershell
docker build -t bibtex-verifier .
```

Run the container using the local environment file:

```powershell
docker run --rm --env-file .env -p 8000:8000 bibtex-verifier
```

Open:

```text
http://127.0.0.1:8000
```

Stop the container with `Ctrl+C`.

## Verification status meanings

- **Verified**: The submitted metadata agrees with strong external evidence.
- **Auto-Updated**: Strong evidence supports one or more suggested metadata corrections or additions.
- **Needs Review**: Available evidence is uncertain, incomplete, or conflicting.
- **Not Found**: No sufficiently reliable matching record was found.
- **Duplicate**: Multiple input entries appear to represent the same publication.

A high confidence score means that the available sources strongly agree. It does not guarantee that every external database record is correct.

## Troubleshooting

### The application does not start

Confirm that the virtual environment is active and reinstall the project:

```powershell
pip install -e ".[dev]"
```

### Port 8000 is already in use

Run the application on another port:

```powershell
uvicorn bibtex_verifier.api:app --reload --port 8001
```

Then open `http://127.0.0.1:8001`.

### A metadata provider fails

The verifier can continue using the other providers. Check the report warnings and confirm that the computer has internet access and that the API configuration in `.env` is correct.

### The browser reports `/favicon.ico` as 404

This is harmless. It only means that a browser-tab icon has not been added and does not affect verification.

## Security

- Keep `.env` private.
- Do not commit API keys.
- Review suggested bibliography changes before accepting them.
- Do not expose the development server directly to the public internet.
- See `SECURITY.md` for reporting security issues.