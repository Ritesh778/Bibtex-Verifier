import httpx

from bibtex_verifier.api import (
    app,
    lifespan,
)


async def test_health_endpoint() -> None:
    async with lifespan(app):
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.get("/health")

    assert response.status_code == 200

    assert response.json() == {
        "status": "ok",
        "version": "0.2.0",
    }


async def test_verify_rejects_empty_request() -> None:
    async with lifespan(app):
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/verify",
                json={"bibtex": ""},
            )

    assert response.status_code == 422


async def test_verify_rejects_unsafe_bibtex() -> None:
    payload = {"bibtex": ('@string{venue="ACL"}\n@article{x,title={Test},booktitle=venue}')}

    async with lifespan(app):
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/verify",
                json=payload,
            )

    assert response.status_code == 422

    detail = response.json()["detail"]

    assert "String macros" in detail
