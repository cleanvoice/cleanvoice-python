"""Integration tests for Cleanvoice SDK with real API endpoints.

These tests require a valid API key and internet connection.
They are marked as 'integration' and can be skipped during regular testing.

To run integration tests:
    pytest tests/test_integration.py -m integration

To skip integration tests:
    pytest -m "not integration"

Set environment variables:
    CLEANVOICE_API_KEY=your-api-key
    CLEANVOICE_TEST_AUDIO_URL=https://example.com/test-audio.mp3
"""

import os
import time
from typing import Optional

import pytest

from cleanvoice import ApiError, Cleanvoice, ProcessingConfig


# Test configuration
TEST_API_KEY = os.getenv("CLEANVOICE_API_KEY")
TEST_AUDIO_URL = os.getenv(
    "CLEANVOICE_TEST_AUDIO_URL",
    "https://www2.cs.uic.edu/~i101/SoundFiles/BabyElephantWalk60.wav"  # Public test file
)
TEST_BASE_URL = os.getenv("CLEANVOICE_BASE_URL", "https://api.cleanvoice.ai/v2")

# Skip all tests if no API key provided
pytestmark = pytest.mark.skipif(
    not TEST_API_KEY,
    reason="CLEANVOICE_API_KEY environment variable not set"
)


@pytest.fixture
def cleanvoice_client():
    """Create a real Cleanvoice client for integration testing."""
    return Cleanvoice({
        'api_key': TEST_API_KEY,
        'base_url': TEST_BASE_URL,
        'timeout': 120  # Longer timeout for real API calls
    })


@pytest.mark.integration
class TestCleanvoiceIntegration:
    """Integration tests using real API endpoints."""

    def test_authentication(self, cleanvoice_client):
        """Test authentication with real API."""
        try:
            result = cleanvoice_client.check_auth()
            assert isinstance(result, dict)
            # Should contain account information
            assert 'user' in result or 'account' in result or len(result) > 0
        except ApiError as e:
            if e.status_code == 401:
                pytest.fail("Authentication failed - check your API key")
            else:
                pytest.fail(f"Unexpected API error: {e}")

    def test_invalid_authentication(self):
        """Test authentication with invalid API key."""
        invalid_client = Cleanvoice({
            'api_key': 'invalid-key-12345',
            'base_url': TEST_BASE_URL
        })
        
        with pytest.raises(ApiError) as exc_info:
            invalid_client.check_auth()
        
        assert exc_info.value.status_code == 401

    def test_create_edit_basic(self, cleanvoice_client):
        """Test creating a basic edit job."""
        edit_id = cleanvoice_client.create_edit(
            TEST_AUDIO_URL,
            {'fillers': True, 'normalize': True}
        )
        
        assert isinstance(edit_id, str)
        assert len(edit_id) > 0
        
        # Verify we can retrieve the edit
        edit_status = cleanvoice_client.get_edit(edit_id)
        assert isinstance(edit_status.status, str)
        assert len(edit_status.status) > 0
        assert edit_status.task_id == edit_id

    def test_create_edit_with_transcription(self, cleanvoice_client):
        """Test creating an edit with transcription enabled."""
        edit_id = cleanvoice_client.create_edit(
            TEST_AUDIO_URL,
            {
                'fillers': True,
                'transcription': True,
                'normalize': True
            }
        )
        
        assert isinstance(edit_id, str)
        assert len(edit_id) > 0

    def test_invalid_file_url(self, cleanvoice_client):
        """Test error handling with invalid file URL."""
        with pytest.raises(Exception):  # Could be ApiError or FileValidationError
            cleanvoice_client.create_edit(
                'https://example.com/nonexistent-file.mp3',
                {'fillers': True}
            )

    def test_invalid_config_validation(self, cleanvoice_client):
        """Test server-side config validation."""
        with pytest.raises(Exception):  # Server should reject invalid config
            cleanvoice_client.create_edit(
                TEST_AUDIO_URL,
                {'invalid_option': True}
            )

    def test_get_nonexistent_edit(self, cleanvoice_client):
        """Test retrieving a non-existent edit."""
        with pytest.raises(ApiError) as exc_info:
            cleanvoice_client.get_edit('nonexistent-edit-id-12345')
        
        assert exc_info.value.status_code in [404, 400]

    @pytest.mark.slow
    def test_full_processing_workflow(self, cleanvoice_client):
        """Test complete processing workflow from start to finish.
        
        Warning: This test may take several minutes to complete.
        """
        progress_updates = []
        
        def progress_callback(data):
            progress_updates.append(data)
            print(f"Progress: {data.get('status')} - Attempt {data.get('attempt', 1)}")
        
        try:
            # Process a small audio file
            result = cleanvoice_client.process(
                TEST_AUDIO_URL,
                {
                    'fillers': True,
                    'normalize': True,
                    'transcription': False  # Skip transcription for faster processing
                },
                progress_callback=progress_callback
            )
            
            # Verify result structure
            assert hasattr(result, 'audio')
            assert hasattr(result.audio, 'url')
            assert hasattr(result.audio, 'filename')
            assert hasattr(result.audio, 'statistics')
            
            # Verify we got progress updates
            assert len(progress_updates) > 0
            
            # Verify final status was SUCCESS
            final_update = progress_updates[-1]
            assert final_update['status'] == 'SUCCESS'
            
            # Verify download URL is accessible
            assert result.audio.url.startswith('http')
            
        except ApiError as e:
            if e.status_code == 402:  # Payment required
                pytest.skip("Account has insufficient credits for processing")
            elif e.status_code == 429:  # Rate limited
                pytest.skip("Rate limited - try again later")
            else:
                raise

    @pytest.mark.slow
    def test_processing_with_transcription(self, cleanvoice_client):
        """Test processing with transcription enabled.
        
        Warning: This test may take several minutes and consume credits.
        """
        try:
            result = cleanvoice_client.process(
                TEST_AUDIO_URL,
                {
                    'fillers': True,
                    'transcription': True,
                    'normalize': True
                }
            )
            
            # Verify audio result
            assert hasattr(result, 'audio')
            assert result.audio.url.startswith('http')
            
            # Verify transcription result if available
            if hasattr(result, 'transcript') and result.transcript:
                assert hasattr(result.transcript, 'text')
                assert hasattr(result.transcript, 'paragraphs')
                assert isinstance(result.transcript.text, str)
                assert len(result.transcript.text) > 0
            
        except ApiError as e:
            if e.status_code == 402:
                pytest.skip("Account has insufficient credits for transcription")
            elif e.status_code == 429:
                pytest.skip("Rate limited - try again later")
            else:
                raise

    def test_concurrent_edit_creation(self, cleanvoice_client):
        """Test creating multiple edits concurrently."""
        import threading
        
        edit_ids = []
        errors = []
        
        def create_edit():
            try:
                edit_id = cleanvoice_client.create_edit(
                    TEST_AUDIO_URL,
                    {'normalize': True}
                )
                edit_ids.append(edit_id)
            except Exception as e:
                errors.append(e)
        
        # Create 3 edits concurrently
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=create_edit)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Check results
        if errors:
            # Some errors are acceptable (rate limiting, etc.)
            print(f"Errors during concurrent creation: {errors}")
        
        # At least one should succeed
        assert len(edit_ids) > 0
        
        # All edit IDs should be unique
        assert len(edit_ids) == len(set(edit_ids))

    def test_polling_timeout_behavior(self, cleanvoice_client):
        """Test polling behavior with very short timeout."""
        edit_id = cleanvoice_client.create_edit(
            TEST_AUDIO_URL,
            {'fillers': True}
        )
        
        # Test polling with very short timeout
        with pytest.raises(ApiError, match="timeout"):
            cleanvoice_client._poll_for_completion(
                edit_id,
                max_attempts=2,  # Very short
                initial_delay=0.1
            )

    def test_different_base_urls(self):
        """Test behavior with different base URLs."""
        # Test with invalid base URL
        invalid_client = Cleanvoice({
            'api_key': TEST_API_KEY,
            'base_url': 'https://invalid-cleanvoice-api.com'
        })
        
        with pytest.raises(ApiError):
            invalid_client.check_auth()

    def test_network_timeout_handling(self):
        """Test handling of network timeouts."""
        timeout_client = Cleanvoice({
            'api_key': TEST_API_KEY,
            'base_url': TEST_BASE_URL,
            'timeout': 1  # Very short timeout
        })
        
        # This may or may not timeout depending on network speed
        try:
            timeout_client.check_auth()
        except ApiError as e:
            # Timeout errors are acceptable
            assert "timeout" in str(e).lower() or "failed" in str(e).lower()

    def test_large_config_object(self, cleanvoice_client):
        """Test with comprehensive configuration options."""
        config = ProcessingConfig(
            fillers=True,
            stutters=True,
            long_silences=True,
            mouth_sounds=True,
            breath=True,
            remove_noise=True,
            normalize=True,
            mute_lufs=-80.0,
            target_lufs=-16.0,
            export_format='mp3',
            transcription=False,  # Skip to avoid extra costs
            send_email=False
        )
        
        edit_id = cleanvoice_client.create_edit(TEST_AUDIO_URL, config)
        assert isinstance(edit_id, str)
        assert len(edit_id) > 0


@pytest.mark.integration
class TestCleanvoiceErrorHandling:
    """Integration tests focusing on error scenarios."""

    def test_malformed_api_responses(self, cleanvoice_client):
        """Test handling of unexpected API responses."""
        # This test would require mocking at the HTTP level
        # which is complex for integration tests
        pass

    def test_api_rate_limiting(self, cleanvoice_client):
        """Test behavior under rate limiting."""
        # Create many requests quickly to potentially trigger rate limiting
        for i in range(10):
            try:
                cleanvoice_client.check_auth()
                time.sleep(0.1)  # Small delay
            except ApiError as e:
                if e.status_code == 429:
                    # Rate limiting is working correctly
                    assert "rate" in str(e).lower() or "limit" in str(e).lower()
                    break
            except Exception:
                # Other errors are also acceptable
                break

    def test_server_error_handling(self, cleanvoice_client):
        """Test handling of server errors (5xx)."""
        # Server errors are hard to trigger reliably in integration tests
        # This test serves as a placeholder for manual testing scenarios
        pass


# Utility functions for integration testing
def wait_for_edit_completion(
    client: Cleanvoice, 
    edit_id: str, 
    max_wait_time: int = 300
) -> Optional[str]:
    """Wait for an edit to complete and return final status.
    
    Args:
        client: Cleanvoice client
        edit_id: Edit ID to wait for
        max_wait_time: Maximum time to wait in seconds
        
    Returns:
        Final status or None if timeout
    """
    start_time = time.time()
    
    while time.time() - start_time < max_wait_time:
        try:
            edit = client.get_edit(edit_id)
            if edit.status in ['SUCCESS', 'FAILURE']:
                return edit.status
            
            time.sleep(5)  # Wait 5 seconds between checks
            
        except ApiError:
            return None
    
    return None  # Timeout


def verify_audio_url_accessible(url: str) -> bool:
    """Verify that an audio URL is accessible.
    
    Args:
        url: URL to check
        
    Returns:
        True if accessible, False otherwise
    """
    import requests
    
    try:
        response = requests.head(url, timeout=10)
        return response.status_code == 200
    except Exception:
        return False


if __name__ == "__main__":
    # Quick test when run directly
    if not TEST_API_KEY:
        print("Set CLEANVOICE_API_KEY environment variable to run integration tests")
        exit(1)
    
    client = Cleanvoice({'api_key': TEST_API_KEY})
    
    try:
        result = client.check_auth()
        print(f"Authentication successful: {result}")
    except Exception as e:
        print(f"Authentication failed: {e}")
        exit(1)
    
    print("Integration test setup is working!")