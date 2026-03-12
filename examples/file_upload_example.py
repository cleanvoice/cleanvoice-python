#!/usr/bin/env python3
"""Examples focused on local file handling with the Cleanvoice SDK."""

from pathlib import Path

from cleanvoice import Cleanvoice


def main() -> None:
    client = Cleanvoice.from_env()
    sample_file = Path("sample_audio.mp3")

    if not sample_file.exists():
        print(f"Sample file '{sample_file}' not found.")
        return

    print("Example 1: upload only")
    uploaded_url = client.upload_file(str(sample_file))
    print(f"Uploaded URL: {uploaded_url}")

    print("\nExample 2: process local file and save output in one call")
    result = client.process(
        str(sample_file),
        fillers=True,
        normalize=True,
        studio_sound=True,
        output_path="processed_audio.wav",
    )
    print(f"Primary download URL: {result.audio.url}")
    print(f"Saved locally to: {result.audio.local_path}")

    print("\nExample 3: process first, then download later from result object")
    delayed_result = client.process(
        str(sample_file),
        remove_noise=True,
        summarize=True,
    )
    delayed_path = delayed_result.audio.download("processed_later.wav")
    print(f"Downloaded later to: {delayed_path}")


if __name__ == "__main__":
    main()
