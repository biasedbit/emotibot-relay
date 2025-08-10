"""
Tests for the MoodStore implementation.

These tests verify the core functionality of the mood storage system,
including updates, reads, and streaming capabilities.
"""

import asyncio

from emotibot_relay.store import MoodStore


class TestMoodStore:
    """Test suite for MoodStore functionality."""

    def setup_method(self):
        """Set up a fresh MoodStore for each test."""
        self.store = MoodStore()

    async def test_initial_state(self):
        """Test that a new store starts with neutral mood."""
        mood = await self.store.read()
        assert mood.value == "neutral"
        assert mood.timestamp is not None

    async def test_update_and_read(self):
        """Test mood update and retrieval."""
        # Update mood
        updated_mood = await self.store.update("happy")

        # Verify the returned mood
        assert updated_mood.value == "happy"
        assert updated_mood.timestamp is not None

        # Verify we can read it back
        read_mood = await self.store.read()
        assert read_mood.value == "happy"
        assert read_mood.timestamp == updated_mood.timestamp

        # Test subsequent updates replace the previous mood
        mood2 = await self.store.update("sad")
        current_mood = await self.store.read()
        assert current_mood.value == "sad"
        assert current_mood.timestamp != updated_mood.timestamp
        assert current_mood.timestamp == mood2.timestamp

    async def test_streaming(self):
        """Test that two consumers receive streaming mood updates."""
        consumer1_moods = []
        consumer2_moods = []

        # Setup async consumer 1
        async def consumer1():
            async with self.store.stream() as mood_stream:
                async for mood in mood_stream:
                    consumer1_moods.append(mood.value)
                    if len(consumer1_moods) >= 3:  # neutral + 2 updates
                        break

        # Setup async consumer 2
        async def consumer2():
            async with self.store.stream() as mood_stream:
                async for mood in mood_stream:
                    consumer2_moods.append(mood.value)
                    if len(consumer2_moods) >= 3:  # neutral + 2 updates
                        break

        # Start both consumers
        task1 = asyncio.create_task(consumer1())
        task2 = asyncio.create_task(consumer2())

        # Let them set up
        await asyncio.sleep(0.01)

        # Issue two mood updates
        await self.store.update("happy")
        await asyncio.sleep(0.01)  # Small delay between updates
        await self.store.update("sad")

        # Wait with timeout
        try:
            await asyncio.wait_for(asyncio.gather(task1, task2), timeout=2.0)
        except TimeoutError:
            # Cancel both async consumers
            task1.cancel()
            task2.cancel()
            try:
                await asyncio.gather(task1, task2, return_exceptions=True)
            except Exception:
                pass

            print(
                "TIMEOUT: Consumer1 got: "
                f"{consumer1_moods}, "
                "Consumer2 got: "
                f"{consumer2_moods}"
            )
            assert False, "Test timed out"

        # Confirm both consumers receive the updates
        print(f"Consumer1 got: {consumer1_moods}, Consumer2 got: {consumer2_moods}")
        assert len(consumer1_moods) == 3
        assert len(consumer2_moods) == 3
        assert consumer1_moods == ["neutral", "happy", "sad"]
        assert consumer2_moods == ["neutral", "happy", "sad"]
