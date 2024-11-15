import sentry_sdk
from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration


from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from fastapi.staticfiles import StaticFiles

# Lifespan stuff
from piccolo.engine import engine_finder

from Finda_AI.config import config
from Finda_AI.routes import (
    v1,
    base
)

sentry_sdk.init(
    dsn="https://8f32a656c307e084bd1e38232cafd6dd@o4508301907460096.ingest.de.sentry.io/4508301909033040",
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for tracing.
    traces_sample_rate=1.0,
    _experiments={
        # Set continuous_profiling_auto_start to True
        # to automatically start the profiler on when
        # possible.
        "continuous_profiling_auto_start": True,
    },
)



@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the connection pool to the Postgres Database
    try:
        engine = engine_finder()
        await engine.start_connection_pool()
    except Exception:
        sentry_sdk.capture_exception(
            Exception(
                "Exception happened during startup: Unable to connect to the database"
                " instance"
            )
        )
        print(
            "\nException happened during startup: Unable to connect to the database"
            " instance\n"
        )

    yield

    # Shutdown the connections to the Postgres Database
    try:
        engine = engine_finder()
        await engine.close_connection_pool()
    except Exception:
        sentry_sdk.capture_exception(
            Exception(
                "Exception happened during shutdown: Unable to connect to the postgres"
                " instance"
            )
        )
        print(
            "\nException happened during shutdown: Unable to connect to the database"
            " instance\n"
        )


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(v1.router)
app.include_router(base.router)