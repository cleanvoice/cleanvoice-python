"""Batch processing example."""

import time
from cleanvoice import Cleanvoice

def main():
    # Initialize SDK
    cv = Cleanvoice.from_env()
    
    # List of audio files to process
    audio_files = [
        "https://example.com/podcast1.mp3",
        "https://example.com/podcast2.mp3", 
        "https://example.com/podcast3.mp3",
    ]
    
    print(f"Starting batch processing of {len(audio_files)} files...")
    
    # Create all edit jobs
    edit_ids = []
    for i, file_url in enumerate(audio_files):
        print(f"Creating edit job {i+1}/{len(audio_files)}...")
        edit_id = cv.create_edit(
            file_url,
            fillers=True,
            normalize=True,
            summarize=True,
        )
        edit_ids.append((edit_id, file_url))
    
    print(f"Created {len(edit_ids)} edit jobs. Polling for completion...")
    
    # Poll for completion
    completed = []
    while edit_ids:
        for edit_id, file_url in edit_ids[:]:  # Create a copy to iterate
            edit = cv.get_edit(edit_id)
            
            if edit.status == 'SUCCESS':
                print(f"✅ Completed: {file_url}")
                completed.append((edit_id, file_url, edit.result))
                edit_ids.remove((edit_id, file_url))
                
            elif edit.status == 'FAILURE':
                print(f"❌ Failed: {file_url}")
                edit_ids.remove((edit_id, file_url))
                
            else:
                # Still processing
                progress = ""
                if edit.result and hasattr(edit.result, 'done'):
                    progress = f" ({edit.result.done}%)"
                print(f"⏳ {edit.status}{progress}: {file_url}")
        
        if edit_ids:  # If there are still jobs running
            time.sleep(5)  # Wait 5 seconds before next poll
    
    print(f"\n🎉 Batch processing complete! {len(completed)} files processed.")
    
    # Display results
    for edit_id, file_url, result in completed:
        print(f"\n📁 {file_url}")
        print(f"   Download: {result.download_url}")
        if result.transcription:
            summary = result.summarization.summary if result.summarization else "No summary"
            print(f"   Summary: {summary[:100]}...")

if __name__ == "__main__":
    main()