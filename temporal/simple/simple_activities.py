"""
Simple hello world activities for Temporal workflow demonstration.

These activities show the basic pattern of Temporal activity definitions
without the complexity of the course sync implementation.
"""

import asyncio
from temporalio import activity


class SimpleActivities:
    """Simple activities for demonstration purposes."""

    @activity.defn
    async def say_hello(self, name: str) -> str:
        """
        Simple activity that says hello to a name.

        Args:
            name: The name to greet

        Returns:
            A greeting message
        """
        activity.logger.info(f"Saying hello to {name}")

        # Simulate some work
        await asyncio.sleep(1)

        greeting = f"Hello, {name}! This is from a Temporal activity."

        activity.logger.info(f"Generated greeting: {greeting}")
        return greeting

    @activity.defn
    async def count_letters(self, text: str) -> int:
        """
        Activity that counts letters in text.

        Args:
            text: The text to count letters in

        Returns:
            Number of letters in the text
        """
        activity.logger.info(f"Counting letters in: '{text}'")

        # Simulate some processing time
        await asyncio.sleep(0.5)

        letter_count = len([c for c in text if c.isalpha()])

        activity.logger.info(f"Found {letter_count} letters")
        return letter_count

    @activity.defn
    async def create_summary(self, letter_count: int) -> dict:
        """
        Activity that creates a summary of the workflow results.

        Args:
            name: The original name
            greeting: The greeting message
            letter_count: Number of letters counted

        Returns:
            Summary dictionary
        """
        activity.logger.info("Creating workflow summary")

        summary = {
            "name": letter_count,
            "workflow_complete": True
        }

        activity.logger.info(f"Summary created: {summary}")
        return summary
