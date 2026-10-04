import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from archguard import __version__
from archguard.api.schemas import HealthResponse, SystemInfoResponse
from archguard.application.system import get_system_information
from archguard.infrastructure.logging import configure_logging
from archguard.infrastructure.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    configuration = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(configuration.log_level)
        logger = logging.getLogger("archguard.api")
        logger.info("API started (%s)", configuration.environment.value)
        try:
            yield
        finally:
            logger.info("API stopped")

    app = FastAPI(
        title=configuration.app_name,
        version=__version__,
        debug=configuration.debug,
        lifespan=lifespan,
    )

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse()

    @app.get("/api/v1/system/info", response_model=SystemInfoResponse, tags=["system"])
    def system_info() -> SystemInfoResponse:
        information = get_system_information(configuration.app_name)
        return SystemInfoResponse.model_validate(information, from_attributes=True)

    return app
