import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__
from .models import VerificationReport
from .parser import BibtexInputError
from .service import VerificationService


class VerifyRequest(BaseModel):
    bibtex: str = Field(
        min_length=1,
        max_length=5 * 1024 * 1024,
    )


@asynccontextmanager
async def lifespan(
    app: FastAPI,
) -> AsyncIterator[None]:
    app.state.verifier = VerificationService()

    yield

    await app.state.verifier.close()


app = FastAPI(
    title="BibTeX Verifier",
    description=("Verify BibTeX references using evidence from multiple scholarly databases."),
    version=__version__,
    lifespan=lifespan,
)


default_origins = (
    "http://127.0.0.1:3000,http://localhost:3000,http://127.0.0.1:5500,http://localhost:5500"
)


allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        default_origins,
    ).split(",")
    if origin.strip()
]


app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=[
        "GET",
        "POST",
    ],
    allow_headers=[
        "Content-Type",
    ],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "version": __version__,
    }


@app.post(
    "/api/v1/verify",
    response_model=VerificationReport,
)
async def verify(
    request: VerifyRequest,
) -> VerificationReport:
    try:
        return await app.state.verifier.verify_bibtex(request.bibtex)

    except BibtexInputError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


ui_directory = Path(
    os.getenv(
        "BIBTEX_UI_DIR",
        Path.cwd() / "docs",
    )
).resolve()


if ui_directory.is_dir():
    app.mount(
        "/",
        StaticFiles(
            directory=ui_directory,
            html=True,
        ),
        name="ui",
    )
