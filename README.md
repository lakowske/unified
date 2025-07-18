# unified

A stack of network tools built around a single database.

## Features

- Modern Python project structure
- Comprehensive testing with pytest and coverage reporting
- Code quality tools (Ruff for linting/formatting, MyPy for type checking)
- Pre-commit hooks for automated quality checks
- GitHub Actions CI/CD pipeline
- VS Code tasks integration

## Quick Start

### Prerequisites

- Python 3.8 or higher
- Git

### Installation

1. Clone the repository:

```bash
git clone https://github.com/lakowske/unified.git
cd unified
```

2. Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install the project in development mode:

```bash
pip install -e ".[dev]"
```

4. Install pre-commit hooks:

```bash
pre-commit install
```

## Development

### Running Tests

```bash
# Run tests with coverage
pytest --cov=. --cov-report=term-missing --cov-fail-under=80 --cov-report=html

# Or use VS Code: Ctrl+Shift+P -> "Tasks: Run Task" -> "Run Tests with Coverage"
```

### Code Quality

```bash
# Format code
ruff format .

# Lint code
ruff check .

# Run all pre-commit checks
pre-commit run --all-files
```

### VS Code Integration

This project includes VS Code tasks for common operations:

- `Ctrl+Shift+P` -> "Tasks: Run Task" to see all available tasks
- Install the "Task Explorer" extension for a better task management experience

## Project Structure

```
unified/
├── src/unified/     # Main package
├── tests/                          # Test suite
├── .github/workflows/              # GitHub Actions
├── .vscode/                        # VS Code configuration
├── pyproject.toml                  # Project configuration
└── README.md                       # This file
```

## Docker Compose Infrastructure

This project includes a comprehensive Docker Compose setup for development and production environments with mail, DNS, web, and database services.

### Starting the Environment

```bash
# Start development environment
docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml up -d

# Stop development environment
docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml down

# View logs
docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml logs [service]
```

### User Management

The system provides REST API endpoints for user management. Get the API key from the running container:

```bash
# Get API key for authenticated requests
API_KEY=$(docker exec apache-dev cat /var/local/unified_api_key)
```

#### Create a User

```bash
# Create an admin user
curl -X POST http://localhost:8080/api/v1/admin/create_user \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "username": "admin",
    "password": "secure-password",
    "email": "admin@example.com",
    "role": "admin"
  }'

# Create a regular user
curl -X POST http://localhost:8080/api/v1/admin/create_user \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "username": "testuser",
    "password": "secure-password",
    "email": "user@example.com",
    "role": "user"
  }'
```

#### List Users

```bash
# List all users
curl -X GET http://localhost:8080/api/v1/admin/list_users \
  -H "X-API-Key: $API_KEY"

# List users with specific role
curl -X GET "http://localhost:8080/api/v1/admin/list_users?role=admin" \
  -H "X-API-Key: $API_KEY"
```

#### Delete a User

```bash
# Delete user by username
curl -X DELETE http://localhost:8080/api/v1/admin/delete_user \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"username": "testuser"}'

# Delete user by ID
curl -X DELETE http://localhost:8080/api/v1/admin/delete_user \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"user_id": "123"}'
```

### Database Management

The project uses Flyway for database migrations:

```bash
# Apply database migrations
docker compose run --rm flyway migrate

# Check migration status
docker compose run --rm flyway info

# Validate migrations
docker compose run --rm flyway validate
```

## Contributing

1. Fork the repository
1. Create a feature branch: `git checkout -b feature/amazing-feature`
1. Make your changes and run the quality checks
1. Commit your changes: `git commit -m 'Add amazing feature'`
1. Push to the branch: `git push origin feature/amazing-feature`
1. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Author

Seth Lakowske - lakowske@gmail.com
