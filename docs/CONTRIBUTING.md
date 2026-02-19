# Contributing to Node Health Monitor

First off, thank you for considering contributing to Node Health Monitor! It's people like you that make this tool better for everyone.

## Code of Conduct

This project and everyone participating in it is governed by our commitment to a welcoming and inclusive environment. By participating, you are expected to uphold this standard.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check existing issues to avoid duplicates. When you create a bug report, include as many details as possible:

- **Use a clear and descriptive title**
- **Describe the exact steps to reproduce the problem**
- **Provide specific examples** (config snippets, command output)
- **Describe the behavior you observed and what you expected**
- **Include your environment details** (Python version, OS, etc.)

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion:

- **Use a clear and descriptive title**
- **Provide a detailed description of the suggested enhancement**
- **Explain why this enhancement would be useful**
- **List any alternatives you've considered**

### Pull Requests

1. Fork the repo and create your branch from `main`
2. If you've added code that should be tested, add tests
3. Ensure the test suite passes (`pytest`)
4. Make sure your code follows the style guidelines (`ruff`, `black`)
5. Issue the pull request

## Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/node-health-monitor.git
cd node-health-monitor

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install in development mode with all dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_models.py

# Run with verbose output
pytest -v
```

## Code Style

We use:
- **Black** for code formatting
- **Ruff** for linting
- **mypy** for type checking

```bash
# Format code
black src tests

# Check linting
ruff check src tests

# Type checking
mypy src
```

## Project Structure

```
node-health-monitor/
├── src/node_health_monitor/
│   ├── __init__.py          # Package exports
│   ├── cli.py               # CLI commands (Click)
│   ├── config.py            # Configuration handling
│   ├── models.py            # Data models
│   ├── monitor.py           # Core monitoring logic
│   ├── collectors/          # Health data collectors
│   │   ├── base.py          # Base collector interface
│   │   ├── local.py         # Local system (psutil)
│   │   └── ssh.py           # Remote via SSH
│   ├── notifiers/           # Alert handlers
│   │   ├── base.py          # Base notifier interface
│   │   ├── telegram.py
│   │   ├── slack.py
│   │   └── webhook.py
│   ├── dashboard/           # Web dashboard
│   │   ├── app.py           # FastAPI application
│   │   └── templates/       # Jinja2 templates
│   └── remediation/         # Auto-remediation
│       └── handler.py
├── tests/                   # Test suite
├── examples/                # Example configurations
├── docs/                    # Documentation
└── pyproject.toml          # Package configuration
```

## Adding a New Collector

1. Create a new file in `src/node_health_monitor/collectors/`
2. Inherit from `BaseCollector`
3. Implement `collect()`, `check_service()`, and `execute_command()`
4. Add to `collectors/__init__.py`
5. Write tests in `tests/test_collectors.py`

## Adding a New Notifier

1. Create a new file in `src/node_health_monitor/notifiers/`
2. Inherit from `BaseNotifier`
3. Implement `send_alert()` and `send_recovery()`
4. Add to `notifiers/__init__.py`
5. Update `config.py` to support new notifier config
6. Write tests

## Commit Messages

- Use the present tense ("Add feature" not "Added feature")
- Use the imperative mood ("Move cursor to..." not "Moves cursor to...")
- Limit the first line to 72 characters or less
- Reference issues and pull requests liberally after the first line

## Questions?

Feel free to open an issue with your question or reach out to the maintainers.

Thank you for contributing! 🎉
