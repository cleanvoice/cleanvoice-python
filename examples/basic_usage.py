"""Basic usage example for Cleanvoice Python SDK."""

from cleanvoice import Cleanvoice

def main():
    # Initialize SDK with your API key
    cv = Cleanvoice({
        'api_key': 'your-api-key-here'  # Replace with your actual API key
    })
    
    # Basic audio processing
    print("Processing audio file...")
    
    result = cv.process(
        "https://example.com/sample-audio.mp3",  # Replace with your audio URL
        {
            'fillers': True,        # Remove filler sounds
            'normalize': True,      # Normalize audio levels
            'remove_noise': True,   # Remove background noise
            'transcription': True,  # Generate transcript
        }
    )
    
    print(f"✅ Processing complete!")
    print(f"📁 Download URL: {result.audio.url}")
    print(f"📊 Statistics: {result.audio.statistics}")
    
    if result.transcript:
        print(f"📝 Transcript: {result.transcript.text[:100]}...")

if __name__ == "__main__":
    main()