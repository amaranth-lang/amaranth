# Amaranth HDL Development Guide

## Build and Test Commands
```bash
# Install dependencies
pdm install

# Run all tests
pdm run test

# Run code tests only
pdm run test-code

# Run a single test
python -m unittest tests.test_module.TestClass.test_method

# Run documentation tests
pdm run test-docs

# Generate coverage reports
pdm run coverage-text
pdm run coverage-html
```

## Code Style Guidelines
- **Imports**: Group by standard library, then project imports
- **Naming**: Classes use PascalCase, functions/methods use snake_case, constants use UPPER_SNAKE_CASE
- **Types**: Type hints are minimal but encouraged in new code
- **Testing**: Test classes extend FHDLTestCase from tests/utils.py
- **Assertions**: Use self.assertEqual(), self.assertRaisesRegex(), etc. in tests
- **Error Handling**: Use ValueError/TypeError with descriptive messages for validation
- **Documentation**: Use Sphinx-compatible docstrings for all public APIs
- **Formatting**: 4-space indentation, 100-character line limit recommended