import asyncio

GEMINI_CONCURRENCY = 2
_gemini_semaphore = asyncio.Semaphore(GEMINI_CONCURRENCY)


async def run_gemini_task(coro):
    async with _gemini_semaphore:
        return await coro
