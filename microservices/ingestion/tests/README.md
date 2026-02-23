# Run a single test file with verbose output and print statements visible
pytest test_checksum.py -v -s

# Run all tests in the directory
pytest -v -s

# Run specific test class
pytest test_checksum.py::TestSha256File -v -s

# Run specific test method
pytest test_checksum.py::TestSha256File::test_deterministic -v -s