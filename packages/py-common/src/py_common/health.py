from fastapi import APIRouter


def health_router() -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return router
