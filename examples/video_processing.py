"""Focused example for video inputs and automatic video detection."""

from cleanvoice import Cleanvoice


def main() -> None:
    client = Cleanvoice.from_env()
    video_url = "https://download.samplelib.com/mp4/sample-5s.mp4"

    print("Processing video file...")
    print("The SDK will auto-detect the .mp4 input and warn before forcing video=True.")

    def progress_callback(data) -> None:
        result = data.get("result")
        done = result.get("done") if isinstance(result, dict) else None
        if done is not None:
            print(f"Progress: {done}%")
        else:
            print(f"Status: {data.get('status')}")

    try:
        result = client.process(
            video_url,
            studio_sound=True,
            remove_noise=True,
            transcription=True,
            summarize=True,
            output_path="processed_video.mp4",
            progress_callback=progress_callback,
        )
    finally:
        client.close()

    print("Video processing complete")
    print(f"Returned media type: {'video' if result.is_video else 'audio'}")
    print(f"Processed file: {result.media.url}")
    print(f"Saved locally: {result.media.local_path}")

    if result.transcript:
        print(f"Transcript preview: {result.transcript.text[:100]}...")


if __name__ == "__main__":
    main()