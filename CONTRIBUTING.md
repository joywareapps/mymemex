# Contributing to MyMemex

Thank you for your interest in contributing to MyMemex! We welcome contributions of all kinds, including bug reports, feature requests, documentation improvements, and code changes.

## 🚀 How to Help

### 🐛 Reporting Bugs
- Search existing [Issues](https://github.com/joywareapps/mymemex/issues) before opening a new one.
- Use the Bug Report template if available.
- Include details about your environment (OS, Docker version, Ollama version).
- Provide steps to reproduce the issue.

### 💡 Feature Requests
- Open an issue with the [Feature Request] prefix.
- Describe the use case and why this feature is valuable.
- For major architectural changes, please open a Discussion first.

### 🛠️ Development Setup
1. Fork the repository.
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/mymemex.git`
3. Create a virtual environment: `python -m venv venv`
4. Install dev dependencies: `pip install -e ".[dev,ocr,ai,mcp]"`
5. Install pre-commit hooks: `pip install pre-commit && pre-commit install`

### 🧪 Running Tests
- Run all tests: `pytest`
- Run with coverage: `pytest --cov=mymemex`
- Integration tests (requires Ollama): `pytest -m integration`

### 📝 Pull Request Process
1. Create a branch: `git checkout -b feature/your-feature-name`
2. Make your changes and ensure tests pass.
3. Run linting: `ruff check .`
4. Commit with clear messages.
5. Push to your fork and open a PR.
6. Link any relevant issues.

## ⚖️ Code of Conduct
Please be respectful and professional in all interactions within this project.

## 📜 License
By contributing to MyMemex, you agree that your contributions will be licensed under the project's [AGPL v3 License](LICENSE).
