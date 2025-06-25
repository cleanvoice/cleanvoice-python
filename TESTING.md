# Testing Guide

This document provides comprehensive information about testing the Cleanvoice Python SDK.

## Test Types

### Unit Tests
Fast, isolated tests that don't require external dependencies or API calls.

```bash
# Run all unit tests
pytest tests/ -m "not integration"

# Run with coverage
pytest tests/ -m "not integration" --cov=cleanvoice --cov-report=term-missing

# Run specific test files
pytest tests/test_basic.py tests/test_client.py
```

### Integration Tests
Tests that interact with real Cleanvoice API endpoints. These require:
- Valid API key
- Internet connection  
- May consume API credits

```bash
# Set up environment
export CLEANVOICE_API_KEY=your-api-key-here

# Run integration tests
pytest tests/test_integration.py -m integration

# Or use the helper script
python run_integration_tests.py
```

## Environment Variables

### Required for Integration Tests
- `CLEANVOICE_API_KEY`: Your Cleanvoice API key

### Optional
- `CLEANVOICE_BASE_URL`: Custom API base URL (default: https://api.cleanvoice.ai/v2)
- `CLEANVOICE_TEST_AUDIO_URL`: Custom test audio file URL

## Test Commands

### Quick Test Suite (Unit Tests Only)
```bash
pytest tests/ -m "not integration" --tb=short
```

### Full Test Suite (Including Integration)
```bash
# Set API key first
export CLEANVOICE_API_KEY=your-key-here

# Run all tests
pytest tests/ --tb=short
```

### Integration Tests Only
```bash
# Quick integration tests (fast)
python run_integration_tests.py quick

# All integration tests (may take several minutes)
python run_integration_tests.py all

# Slow integration tests only
python run_integration_tests.py slow
```

### Test with Coverage
```bash
pytest tests/ -m "not integration" --cov=cleanvoice --cov-report=html
# Open htmlcov/index.html to view coverage report
```

## Test Markers

Tests are marked with pytest markers to control execution:

- `@pytest.mark.integration`: Requires real API, may consume credits
- `@pytest.mark.slow`: Long-running tests (>30 seconds)
- `@pytest.mark.unit`: Fast unit tests (default)

### Running Specific Markers
```bash
# Only integration tests
pytest -m integration

# Only slow tests
pytest -m slow

# Integration but not slow
pytest -m "integration and not slow"

# Everything except integration
pytest -m "not integration"
```

## Test Structure

```
tests/
├── test_basic.py              # Basic SDK functionality
├── test_client.py             # API client HTTP interactions  
├── test_process_method.py     # Process method comprehensive tests
├── test_error_handling.py     # Error scenarios and edge cases
├── test_file_handler.py       # File validation utilities
├── test_file_handler_advanced.py  # Advanced file handling (incomplete)
└── test_integration.py        # Real API integration tests
```

## Integration Test Categories

### Authentication Tests
- Valid API key authentication
- Invalid API key handling
- Different base URL configurations

### Basic Workflow Tests  
- Create edit jobs
- Retrieve edit status
- Basic audio processing

### Advanced Workflow Tests
- Full processing with polling
- Transcription and summarization
- Progress callback functionality

### Error Handling Tests
- Invalid file URLs
- Server errors and rate limiting
- Network timeout handling

### Performance Tests
- Concurrent API calls
- Polling timeout behavior
- Large configuration objects

## Continuous Integration

For CI/CD pipelines, use unit tests by default:

```yaml
# GitHub Actions example
- name: Run tests
  run: pytest tests/ -m "not integration" --cov=cleanvoice

# Only run integration tests if API key is available
- name: Run integration tests
  if: ${{ secrets.CLEANVOICE_API_KEY }}
  env:
    CLEANVOICE_API_KEY: ${{ secrets.CLEANVOICE_API_KEY }}
  run: pytest tests/test_integration.py -m "integration and not slow"
```

## Troubleshooting

### Common Issues

**Import Errors**
```bash
# Install SDK in development mode
pip install -e .
```

**Integration Test Authentication Failures**
```bash
# Check API key
echo $CLEANVOICE_API_KEY

# Test authentication directly
python -c "
from cleanvoice import Cleanvoice
cv = Cleanvoice({'api_key': '$CLEANVOICE_API_KEY'})
print(cv.check_auth())
"
```

**Network/Timeout Issues**
- Check internet connection
- Verify API endpoint is accessible
- Try increasing timeout values

**Rate Limiting**
- Reduce concurrent test execution
- Add delays between API calls
- Use test API endpoint if available

### Test Data

The integration tests use a public test audio file by default. You can provide your own:

```bash
export CLEANVOICE_TEST_AUDIO_URL=https://your-domain.com/test-audio.mp3
```

Requirements for test audio files:
- Publicly accessible URL
- Valid audio format (mp3, wav, etc.)
- Small file size (< 1MB recommended for tests)
- Short duration (< 30 seconds recommended)

## Best Practices

1. **Run unit tests frequently** during development
2. **Run integration tests** before releases
3. **Use appropriate test markers** to control execution
4. **Mock external dependencies** in unit tests
5. **Keep integration tests focused** and fast when possible
6. **Document test requirements** clearly
7. **Use environment variables** for configuration
8. **Handle test cleanup** properly (API resources)

## Coverage Goals

- **Unit Tests**: > 90% line coverage
- **Integration Tests**: Cover all major user workflows
- **Critical Paths**: 100% coverage (authentication, processing, errors)

Current coverage: 73% overall, 100% on core modules.