"""AppError subclasses become JSON error responses through one handler in main."""

from httpx import ASGITransport, AsyncClient

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.main import create_app


async def test_app_errors_become_json_responses():
    app = create_app()

    @app.get("/boom/{kind}")
    async def boom(kind: str):
        raise {
            "missing": NotFoundError,
            "denied": ForbiddenError,
            "clash": ConflictError,
        }[kind]("explained")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for kind, status, code in [
            ("missing", 404, "not_found"),
            ("denied", 403, "forbidden"),
            ("clash", 409, "conflict"),
        ]:
            response = await client.get(f"/boom/{kind}")
            assert response.status_code == status
            assert response.json() == {"error": {"code": code, "message": "explained"}}
