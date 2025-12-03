"""Main FastAPI application entrypoint."""
import uvicorn
from app.api import app
from app.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.api:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True
    )

