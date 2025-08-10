"""
End-to-end tests for the EmotiBot Web API endpoints.

These tests verify the complete HTTP API functionality including mood updates,
retrieval, and Server-Sent Events streaming.
"""

import asyncio
import contextlib
import json
import socket
import threading
import time

import httpx
import uvicorn
from fastapi.testclient import TestClient
from httpx_sse import aconnect_sse

from emotibot_relay.server import create_app
from emotibot_relay.store import MoodStore

# MARK: - Sync


class TestAPISync:
    """Integration tests covering the complete application flow using HTTP
    synchronous request/response flow."""

    def setup_method(self):
        """Set up a fresh app with a new mood store for each test."""
        self.mood_store = MoodStore()
        self.app = create_app(self.mood_store)

    def test_complete_workflow(self):
        """Test the complete workflow: get -> update -> verify -> stream endpoint."""
        with TestClient(self.app) as client:
            # 1. Get initial mood (should be neutral)
            initial_response = client.get("/mood")
            assert initial_response.status_code == 200
            initial_mood = initial_response.json()["mood"]["value"]
            assert initial_mood == "neutral"

            # 2. Update mood to something different
            update_response = client.put("/mood", json={"mood": "productive"})
            assert update_response.status_code == 200

            update_result = update_response.json()
            assert update_result["mood"]["value"] == "productive"
            assert update_result["mood"]["timestamp"] is not None

            # 3. Verify mood was stored by fetching it again
            get_response = client.get("/mood")
            assert get_response.status_code == 200

            mood_data = get_response.json()["mood"]
            assert mood_data["value"] == "productive"
            assert mood_data["timestamp"] == update_result["mood"]["timestamp"]

            # 4. Update to a second mood to test the workflow continues working
            second_update = client.put("/mood", json={"mood": "relaxed"})
            assert second_update.status_code == 200
            assert second_update.json()["mood"]["value"] == "relaxed"

            # 5. Test the streaming functionality directly via the mood store
            # Since we have access to the same mood store instance, we can test
            # that streaming works by using the store's streaming interface
            import asyncio

            async def test_streaming():
                received_moods = []

                async def stream_consumer():
                    async with self.mood_store.stream() as mood_stream:
                        async for mood in mood_stream:
                            received_moods.append(mood.value)
                            if len(received_moods) >= 2:  # Current mood + 1 update
                                break

                # Start the consumer
                consumer_task = asyncio.create_task(stream_consumer())

                # Give it time to connect and get current mood
                await asyncio.sleep(0.01)

                # Make an update via the store (simulating what the API does)
                await self.mood_store.update("streaming_test")

                # Wait for the consumer to get the events
                try:
                    await asyncio.wait_for(consumer_task, timeout=2.0)
                except TimeoutError:
                    consumer_task.cancel()
                    assert False, f"Streaming test timed out. Got: {received_moods}"

                # Verify we got the expected moods
                assert len(received_moods) == 2
                assert received_moods[0] == "relaxed"  # From previous API call
                assert received_moods[1] == "streaming_test"  # From our update

            # Run the async streaming test
            asyncio.run(test_streaming())

            # 6. Verify the stream HTTP endpoint exists and responds correctly
            with client.stream("GET", "/mood/stream") as response:
                assert response.status_code == 200
                assert response.headers["content-type"].startswith("text/event-stream")
                # Just verify the endpoint starts properly, don't consume the stream


# MARK: - Streaming


class TestAPIStream:
    """Integration tests covering the complete application flow using SSE."""

    def setup_method(self):
        """Set up a fresh app with a new mood store for each test."""
        self.mood_store = MoodStore()
        self.app = create_app(self.mood_store)

    async def test_streaming_api(self):
        """Test streaming API with a consumer that collects mood updates."""

        # Start a real HTTP server in a background thread on a free port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        host, port = sock.getsockname()
        sock.close()
        base_url = f"http://{host}:{port}"

        config = uvicorn.Config(
            app=self.app,
            host=host,
            port=port,
            loop="asyncio",
            lifespan="on",
            log_level="warning",
            ws="none",  # Avoid importing deprecated websockets implementation
        )
        server = uvicorn.Server(config)

        def run_server() -> None:
            asyncio.run(server.serve())

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()

        # Wait for server to be ready
        start = time.time()
        while time.time() - start < 5.0:
            try:
                r = httpx.get(base_url + "/", timeout=0.2)
                if r.status_code == 200:
                    break
            except Exception:
                pass
            time.sleep(0.05)
        else:
            server.should_exit = True
            thread.join(timeout=1.0)
            assert False, "Server did not start in time"

        # Now run the async streaming test against the live server
        async with httpx.AsyncClient(
            base_url=base_url, timeout=httpx.Timeout(5.0, read=None)
        ) as client:
            received: list[str] = []
            get_initial_mood = asyncio.Event()

            async def consume() -> None:
                try:
                    async with aconnect_sse(client, "GET", "/mood/stream") as es:
                        assert es.response.status_code == 200
                        content_type = es.response.headers.get("content-type", "")
                        assert content_type.startswith("text/event-stream")

                        async for sse in es.aiter_sse():
                            if sse.event == "error":
                                error_payload = json.loads(sse.data)
                                assert False, f"SSE error event: {error_payload}"

                            payload = json.loads(sse.data)
                            assert "value" in payload
                            received.append(payload["value"])

                            if len(received) == 1:
                                get_initial_mood.set()

                            if len(received) >= 3:
                                break
                except asyncio.CancelledError:
                    raise

            consumer_task = asyncio.create_task(consume())

            # Wait for the consumer to receive the initial event
            try:
                await asyncio.wait_for(get_initial_mood.wait(), timeout=3.0)
            except TimeoutError:
                consumer_task.cancel()
                with contextlib.suppress(Exception):
                    await consumer_task
                server.should_exit = True
                thread.join(timeout=1.0)
                assert False, "Consumer did not receive initial event in time"

            # Issue two updates via the HTTP API
            resp1 = await client.put("/mood", json={"mood": "happy"})
            assert resp1.status_code == 200
            resp2 = await client.put("/mood", json={"mood": "sad"})
            assert resp2.status_code == 200

            # Await consumer completion with a hard timeout
            try:
                await asyncio.wait_for(consumer_task, timeout=3.0)
            except TimeoutError:
                consumer_task.cancel()
                with contextlib.suppress(Exception):
                    await consumer_task
                server.should_exit = True
                thread.join(timeout=1.0)
                assert False, f"Streaming test timed out. Received: {received}"

            # Validate the received sequence and final state
            assert received == ["neutral", "happy", "sad"]

            final = await client.get("/mood")
            assert final.status_code == 200
            assert final.json()["mood"]["value"] == "sad"

        # Shutdown server
        server.should_exit = True
        thread.join(timeout=2.0)
