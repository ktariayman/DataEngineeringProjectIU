# Ingestion Tests

Unit tests for the ingestion microservice.

## Running Tests

```bash
# All tests
pytest -v -s

# Single file
pytest test_checksum.py -v -s

# Single class
pytest test_checksum.py::TestSha256File -v -s

# Single method
pytest test_checksum.py::TestSha256File::test_deterministic -v -s
```
