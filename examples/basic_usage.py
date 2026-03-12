"""Basic usage examples for the Cleanvoice Python SDK."""

from cleanvoice import AsyncCleanvoice, Cleanvoice


def sync_example() -> None:
    """Run a simple synchronous processing flow."""
    client = Cleanvoice.from_env()

    result = client.process(
        "https://example.com/sample-audio.mp3",
        fillers=True,
        normalize=True,
        remove_noise=True,
        studio_sound=True,
        transcription=True,
        output_path="processed_sync.wav",
    )

    print("Sync processing complete")
    print(f"Download URL: {result.audio.url}")
    print(f"Saved locally to: {result.audio.local_path}")

    if result.transcript:
        print(f"Transcript preview: {result.transcript.text[:120]}...")


async def async_example() -> None:
    """Run the same flow with the async client."""
    async with AsyncCleanvoice.from_env() as client:
        result = await client.process(
            "https://example.com/sample-audio.mp3",
            normalize=True,
            studio_sound=True,
            summarize=True,
            output_path="processed_async.wav",
        )

    print("Async processing complete")
    print(f"Saved locally to: {result.audio.local_path}")


if __name__ == "__main__":
    sync_example()
