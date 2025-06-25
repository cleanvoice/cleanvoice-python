"""Video processing example using PyAV without ffmpeg."""

from cleanvoice import Cleanvoice, get_video_info, extract_audio_from_video

def main():
    # Initialize SDK
    cv = Cleanvoice({
        'api_key': 'your-api-key-here'
    })
    
    video_url = "https://example.com/sample-video.mp4"
    
    # Get video information (if you have a local file)
    # info = get_video_info('path/to/video.mp4')
    # print(f"Video info: {info.duration}s, {info.width}x{info.height}")
    
    # Process video file
    print("Processing video file...")
    
    def progress_callback(data):
        if 'result' in data and data['result'] and 'done' in data['result']:
            progress = data['result']['done']
            print(f"Progress: {progress}%")
    
    result = cv.process(
        video_url,
        {
            'video': True,          # Process as video
            'fillers': True,        # Remove fillers from audio
            'normalize': True,      # Normalize audio
            'transcription': True,  # Generate transcript
            'export_format': 'mp3', # Export audio as MP3
        },
        progress_callback=progress_callback
    )
    
    print(f"✅ Video processing complete!")
    print(f"🎵 Audio download: {result.audio.url}")
    
    if result.transcript:
        print(f"📝 Transcript: {result.transcript.text[:100]}...")

if __name__ == "__main__":
    main()