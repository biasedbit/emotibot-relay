"""
FastAPI server for the EmotiBot Web service.

This module implements the HTTP API endpoints for mood updates and Server-Sent
Events streaming. It acts as a relay between HTTP clients updating moods and
SSE clients consuming mood streams.
"""

import asyncio
import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .models import Mood
from .store import MoodStore


# API Request/Response Schemas
class MoodUpdate(BaseModel):
    """Payload for mood update requests."""

    mood: str = Field(..., description="The new mood value to set")


class MoodResponse(BaseModel):
    """Response model for mood endpoints."""

    mood: Mood | None = Field(..., description="The current mood state")


def create_app(mood_store: MoodStore) -> FastAPI:
    """
    Create a FastAPI application with the given mood store.

    Args:
        mood_store: The MoodStore instance to use for the application

    Returns:
        Configured FastAPI application
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """Lifespan context manager for FastAPI application."""
        # Startup
        yield
        # Shutdown - cleanup would go here if needed

    app = FastAPI(
        title="EmotiBot Web",
        description="A mood relay service with HTTP and SSE support",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/")
    async def root() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "ok", "service": "emotibot-relay"}

    @app.get("/mood")
    async def get_mood() -> MoodResponse:
        """
        Get the current mood state.

        Returns:
            The current mood object (defaults to "neutral")
        """
        current_mood = await mood_store.read()
        return MoodResponse(mood=current_mood)

    @app.put("/mood")
    async def update_mood(mood_update: MoodUpdate) -> MoodResponse:
        """
        Update the current mood and notify all subscribers.

        Args:
            mood_update: The mood update payload

        Returns:
            The updated mood object with timestamp
        """
        try:
            updated_mood = await mood_store.update(mood_value=mood_update.mood)
            return MoodResponse(mood=updated_mood)
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to update mood: {str(e)}"
            )

    @app.get("/mood/stream")
    async def stream_mood() -> StreamingResponse:
        """
        Stream mood updates via Server-Sent Events.

        This endpoint establishes an SSE connection and streams all mood updates
        to the client in real-time. The connection includes the current mood
        immediately upon connection.

        Returns:
            StreamingResponse with text/event-stream content type
        """

        async def event_generator() -> AsyncGenerator[str, None]:
            """Generate SSE events for mood updates."""
            try:
                async with mood_store.stream() as mood_stream:
                    async for mood in mood_stream:
                        # Format as Server-Sent Event
                        data = json.dumps(mood.model_dump())
                        yield f"data: {data}\n\n"
            except asyncio.CancelledError:
                # Client disconnected
                pass
            except Exception as e:
                # Send error event and close
                error_data = json.dumps({"error": str(e)})
                yield f"event: error\ndata: {error_data}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
            },
        )

    return app


# Default app instance for backwards compatibility
app = create_app(MoodStore())


def main() -> None:
    """Main entry point for the server."""
    import uvicorn

    uvicorn.run(
        "emotibot_relay.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
