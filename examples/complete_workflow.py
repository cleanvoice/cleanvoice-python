#!/usr/bin/env python3
"""Complete workflow example: local file upload, processing, and result access."""

from pathlib import Path

from cleanvoice import Cleanvoice


def main() -> None:
    client = Cleanvoice.from_env()
    sample_file = Path("sample_audio.mp3")

    if not sample_file.exists():
        print(f"Sample file '{sample_file}' not found.")
        print("Replace it with a real local audio file before running this example.")
        return

    print("Workflow 1: explicit upload then process")
    uploaded_url = client.upload_file(str(sample_file), "episode_source.mp3")
    print(f"Uploaded URL: {uploaded_url}")

    uploaded_result = client.process(
        uploaded_url,
        fillers=True,
        normalize=True,
        summarize=True,
        output_path="episode_uploaded_flow.wav",
    )
    print(f"Uploaded flow saved to: {uploaded_result.audio.local_path}")

    print("\nWorkflow 2: direct local processing with automatic upload and download")
    direct_result = client.process(
        str(sample_file),
        fillers=True,
        remove_noise=True,
        studio_sound=True,
        transcription=True,
        output_path="episode_direct_flow.wav",
    )
    print(f"Direct flow saved to: {direct_result.audio.local_path}")

    if direct_result.transcript:
        print(f"Transcript preview: {direct_result.transcript.text[:150]}...")

    print("\nWorkflow 3: create edit now, fetch later")
    edit_id = client.create_edit(
        str(sample_file),
        normalize=True,
        studio_sound=True,
    )
    print(f"Created edit: {edit_id}")
    print("Use client.get_edit(edit_id) to poll manually in a separate step.")


if __name__ == "__main__":
    main()
