# Development Guide for distomon

This document provides guidelines and instructions for developing and contributing to the distomon project.

## Getting Started

### Prerequisites
- Python 3.8+
- [Poetry](https://python-poetry.org/)
- Docker (optional, for containerized development)

### Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/rippleFCL/distomon.git
   cd distomon
   ```
2. Install dependencies:
   ```bash
   poetry install
   ```
3. (Optional) Set up a virtual environment if not using Poetry's built-in venv.

### Running the Server
To start the server locally:
```bash
poetry run python src/server.py
```

### Running Tests
```bash
poetry run python src/test.py
```

### Linting and Formatting
- Run linting with ruff:
  ```bash
  poetry run ruff src/
  ```
- (Optional) Use pre-commit hooks:
  ```bash
  poetry run pre-commit run --all-files
  ```

## Project Structure

See the main `README.md` for a detailed project structure.

## Making Changes
- Follow PEP8 and project code style.
- Write clear commit messages.
- Add or update tests as needed.
- Document new features or changes.

## Useful Commands
- Install a new dependency:
  ```bash
  poetry add <package>
  ```
- Add a dev dependency:
  ```bash
  poetry add --group dev <package>
  ```
- Update dependencies:
  ```bash
  poetry update
  ```

## Contributing
Pull requests are welcome! Please open an issue to discuss major changes before submitting.

## Support
For questions or support, open an issue on GitHub.
