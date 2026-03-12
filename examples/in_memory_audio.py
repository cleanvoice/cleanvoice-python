#!/usr/bin/env python3
"""Example: process a librosa / NumPy audio array in memory."""

from pathlib import Path

import librosa

from cleanvoice import Cleanvoice


def main() -> None:
    client = Cleanvoice.from_env()
    sample_file = Path("sample_audio.wav")

    if not sample_file.exists():
        print(f"Sample file '{sample_file}' not found.")
        print("Replace it with a real local audio file before running this example.")
        return

    audio, sample_rate = librosa.load(sample_file, sr=None, mono=True)

    try:
        result = client.process(
            (audio, sample_rate),
            studio_sound=True,
            remove_noise=True,
            output_path="processed_from_array.mp3",
        )
    finally:
        client.close()

    print("Processing complete")
    print(f"Saved locally to: {result.media.local_path}")
    print(f"Download URL: {result.media.url}")


if __name__ == "__main__":
    main()
