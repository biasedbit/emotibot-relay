"""
Mood storage implementation for the EmotiBot Web service.

This module provides an in-memory mood store that supports real-time updates
and streaming to multiple subscribers. The design allows for easy replacement
with persistent storage backends like Redis in the future.
"""

import asyncio
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from .models import Mood


class MoodStore:
    """
    In-memory mood storage with real-time streaming capabilities.

    This store maintains the current mood state and provides async streaming
    to multiple subscribers using event-based signaling instead of queues.
    All operations are thread-safe through asyncio primitives.
    """

    def __init__(self) -> None:
        self._current_mood = Mood(value="neutral", timestamp=time.time())
        self._condition = asyncio.Condition()
        self._update_counter = 0  # Simple counter to detect updates

    async def update(self, mood_value: str) -> Mood:
        """
        Update the current mood and notify all subscribers.

        Args:
            mood_value: The new mood value to set

        Returns:
            The updated Mood object with timestamp
        """
        async with self._condition:
            new_mood = Mood(value=mood_value, timestamp=time.time())
            self._current_mood = new_mood
            self._update_counter += 1

            # Notify all waiting subscribers
            self._condition.notify_all()

            return new_mood

    async def read(self) -> Mood:
        """
        Get the current mood state.

        Returns:
            The current Mood object (defaults to "neutral")
        """
        async with self._condition:
            return self._current_mood

    @asynccontextmanager
    async def stream(self) -> AsyncGenerator[AsyncGenerator[Mood, None], None]:
        """
        Stream mood updates to a subscriber.

        This context manager yields an async generator that produces Mood objects
        whenever they are updated. Uses condition variables for efficient signaling.

        Yields:
            An async generator of Mood objects
        """

        async def mood_generator() -> AsyncGenerator[Mood, None]:
            # Get initial state and counter
            async with self._condition:
                last_seen_counter = self._update_counter
                yield self._current_mood

            # Wait for updates
            try:
                while True:
                    async with self._condition:
                        # Wait until there's a new update
                        await self._condition.wait_for(
                            lambda: self._update_counter > last_seen_counter
                        )

                        # Update our counter and yield the current mood
                        last_seen_counter = self._update_counter
                        yield self._current_mood

            except (asyncio.CancelledError, GeneratorExit):
                # Client disconnected or generator closed, clean exit
                return

        yield mood_generator()
