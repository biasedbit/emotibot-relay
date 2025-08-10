"""
Command-line interface tools for the EmotiBot Web service.
"""

import asyncio
import json
from collections.abc import Coroutine
from datetime import datetime
from typing import Any

import httpx
import typer
from httpx_sse import ServerSentEvent, aconnect_sse

from .models import Mood

DEFAULT_BASE_URL = "http://localhost:8000"

app = typer.Typer(help="EmotiBot Web CLI tools")


# MARK: - CLI Entry Points


def cli_set_mood() -> None:
    """Entry point for mood-set CLI command."""
    import typer

    typer.run(set_mood)


def cli_get_mood() -> None:
    """Entry point for mood-get CLI command."""
    import typer

    typer.run(get_mood)


def cli_stream() -> None:
    """Entry point for mood-stream CLI command."""
    import typer

    typer.run(stream)


# MARK: - Commands


@app.command()
def set_mood(
    mood: str = typer.Argument(..., help="The mood value to set"),
    base_url: str = typer.Option(
        DEFAULT_BASE_URL, "--url", "-u", help="Base URL of the EmotiBot service"
    ),
) -> None:
    """Set the current mood on the EmotiBot service."""

    async def _set_mood() -> None:
        async with httpx.AsyncClient() as client:
            response = await client.put(f"{base_url}/mood", json={"mood": mood})
            response.raise_for_status()
            result = response.json()
            print(f"Mood set to: {result['mood']['value']}")

    _run_with_error_handling(_set_mood(), base_url)


@app.command()
def get_mood(
    base_url: str = typer.Option(
        DEFAULT_BASE_URL, "--url", "-u", help="Base URL of the EmotiBot service"
    ),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
) -> None:
    """Get the current mood from the EmotiBot service."""

    async def _get_mood() -> None:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/mood")
            response.raise_for_status()
            result = response.json()

            if json_output:
                print(json.dumps(result, indent=2))
                return

            mood_data = result["mood"]
            if mood_data is None:
                print("No mood set")
            else:
                mood = Mood.model_validate(mood_data)
                print(mood.value)

    _run_with_error_handling(_get_mood(), base_url)


@app.command()
def stream(
    base_url: str = typer.Option(
        DEFAULT_BASE_URL, "--url", "-u", help="Base URL of the EmotiBot service"
    ),
) -> None:
    """Stream mood updates in real-time."""

    async def _stream() -> None:
        print(f"Streaming from {base_url}/mood/stream... (Ctrl+C to stop)")

        async with httpx.AsyncClient(timeout=None) as client:
            async with aconnect_sse(
                client, "GET", f"{base_url}/mood/stream"
            ) as event_source:
                async for sse in event_source.aiter_sse():
                    _handle_sse_event(sse)

    _run_with_error_handling(_stream(), base_url)


# MARK: - Private Helpers


def _format_mood_timestamp(mood: Mood) -> str:
    """Format mood with optional timestamp."""
    if not mood.timestamp:
        return mood.value

    dt = datetime.fromtimestamp(mood.timestamp)
    timestamp = dt.strftime("%H:%M:%S")
    return f"{timestamp} > {mood.value}"


def _handle_sse_event(sse: ServerSentEvent) -> None:
    """Handle a single SSE event."""
    try:
        # Handle error events from server
        if sse.event == "error":
            error_data = json.loads(sse.data)
            print(f"Server error: {error_data.get('error', 'Unknown error')}")
            return

        # Parse mood data using Pydantic model
        raw_data = json.loads(sse.data)

        # Handle error events that come as data
        if "error" in raw_data:
            print(f"Server error: {raw_data['error']}")
            return

        mood = Mood.model_validate(raw_data)
        print(_format_mood_timestamp(mood))

    except json.JSONDecodeError as e:
        print(f"Warning: Could not parse SSE data: {sse.data} - {e}")
    except Exception as e:
        print(f"Warning: Error processing mood data: {e}")


def _run_with_error_handling(coro: Coroutine[Any, Any, Any], base_url: str) -> None:
    """Run an async coroutine with standardized error handling."""
    try:
        asyncio.run(coro)
    except KeyboardInterrupt:
        print("\nStopped")
        raise typer.Exit(0)
    except httpx.ConnectError:
        print(f"Error: Could not connect to {base_url}")
        raise typer.Exit(1)
    except httpx.HTTPStatusError as e:
        print(f"Error: HTTP {e.response.status_code}")
        raise typer.Exit(1)
    except Exception as e:
        error_msg = str(e) if str(e) else f"Unknown error of type {type(e).__name__}"
        print(f"Error: {error_msg}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
