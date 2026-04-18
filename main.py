"""
Chatbot Inteligente para Gestión de Turnos Médicos - WhatsApp
Trabajo Final de Ingeniería Informática

Punto de entrada principal de la aplicación FastAPI.
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import logging

from app.api.v1 import webhook, health
from app.core.config import settings
from app.db.session import init_db

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Aplicación FastAPI
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Chatbot Turnos Médicos",
    description=(
        "API para el chatbot conversacional de gestión de turnos médicos vía WhatsApp. "
        "Implementa NLU con Slot Filling no lineal."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(webhook.router, prefix="/api/v1/webhook", tags=["WhatsApp Webhook"])

# ---------------------------------------------------------------------------
# Eventos de ciclo de vida
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def on_startup():
    logger.info("Iniciando la aplicación...")
    await init_db()
    logger.info("Base de datos inicializada correctamente.")


@app.on_event("shutdown")
async def on_shutdown():
    logger.info("Cerrando la aplicación...")


# ---------------------------------------------------------------------------
# Handler de excepciones global
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Error no manejado: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Error interno del servidor."},
    )


# ---------------------------------------------------------------------------
# Entrypoint local
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
