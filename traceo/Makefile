.PHONY: help install build up down logs test lint format clean

# Colors
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

help:
	@echo "$(BLUE)Traceo Development Commands$(NC)"
	@echo ""
	@echo "$(YELLOW)Setup:$(NC)"
	@echo "  make install              Install dependencies"
	@echo "  make init-env             Initialize .env from .env.example"
	@echo ""
	@echo "$(YELLOW)Docker:$(NC)"
	@echo "  make build                Build Docker images"
	@echo "  make up                   Start all services"
	@echo "  make down                 Stop all services"
	@echo "  make logs                 Show logs from all services"
	@echo "  make logs-backend         Show backend logs only"
	@echo "  make logs-frontend        Show frontend logs only"
	@echo "  make clean-docker         Remove containers and volumes"
	@echo ""
	@echo "$(YELLOW)Development:$(NC)"
	@echo "  make dev-backend          Start backend in development mode"
	@echo "  make dev-frontend         Start frontend in development mode"
	@echo "  make test                 Run all tests"
	@echo "  make test-backend         Run backend tests"
	@echo "  make test-coverage        Run tests with coverage report"
	@echo ""
	@echo "$(YELLOW)Code Quality:$(NC)"
	@echo "  make lint                 Run linters (black, flake8)"
	@echo "  make format               Format code (black, isort)"
	@echo "  make type-check           Run type checker (mypy)"
	@echo ""
	@echo "$(YELLOW)Database:$(NC)"
	@echo "  make db-shell             Connect to PostgreSQL shell"
	@echo "  make db-reset             Reset database"
	@echo "  make db-migrate           Run migrations"
	@echo ""
	@echo "$(YELLOW)Documentation:$(NC)"
	@echo "  make docs                 Generate documentation"
	@echo "  make api-docs             Open API documentation (Swagger UI)"
	@echo ""
	@echo "$(YELLOW)Utilities:$(NC)"
	@echo "  make clean                Clean up generated files"
	@echo "  make translate            Generate 50-language translations"
	@echo "  make health-check         Check service health"
	@echo ""

# ============================================================================
# Setup Commands
# ============================================================================

install:
	@echo "$(BLUE)Installing dependencies...$(NC)"
	pip install -r backend/requirements.txt
	pip install -r backend/requirements-dev.txt
	cd frontend && npm install
	@echo "$(GREEN)✓ Dependencies installed$(NC)"

init-env:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "$(GREEN)✓ .env created from .env.example$(NC)"; \
		echo "$(YELLOW)⚠ Please edit .env with your settings$(NC)"; \
	else \
		echo "$(YELLOW)⚠ .env already exists$(NC)"; \
	fi

# ============================================================================
# Docker Commands
# ============================================================================

build:
	@echo "$(BLUE)Building Docker images...$(NC)"
	docker-compose build
	@echo "$(GREEN)✓ Build complete$(NC)"

up:
	@echo "$(BLUE)Starting services...$(NC)"
	docker-compose up -d
	@echo "$(GREEN)✓ Services started$(NC)"
	@echo ""
	@echo "$(YELLOW)Services running:$(NC)"
	@echo "  Frontend: http://localhost:3000"
	@echo "  Backend:  http://localhost:8000"
	@echo "  API Docs: http://localhost:8000/docs"
	@echo "  Database: postgresql://localhost:5432/traceo"

down:
	@echo "$(BLUE)Stopping services...$(NC)"
	docker-compose down
	@echo "$(GREEN)✓ Services stopped$(NC)"

logs:
	docker-compose logs -f

logs-backend:
	docker-compose logs -f backend

logs-frontend:
	docker-compose logs -f frontend

clean-docker:
	@echo "$(BLUE)Removing containers and volumes...$(NC)"
	docker-compose down -v
	@echo "$(GREEN)✓ Cleaned up$(NC)"

# ============================================================================
# Development Commands
# ============================================================================

dev-backend:
	@echo "$(BLUE)Starting backend in development mode...$(NC)"
	cd backend && python -m uvicorn app.main:app --reload --port 8000

dev-frontend:
	@echo "$(BLUE)Starting frontend in development mode...$(NC)"
	cd frontend && npm start

test:
	@echo "$(BLUE)Running all tests...$(NC)"
	cd backend && pytest tests/ -v
	@echo "$(GREEN)✓ Tests complete$(NC)"

test-backend:
	@echo "$(BLUE)Running backend tests...$(NC)"
	cd backend && pytest tests/ -v

test-coverage:
	@echo "$(BLUE)Running tests with coverage...$(NC)"
	cd backend && pytest tests/ --cov=app --cov-report=html --cov-report=term
	@echo "$(GREEN)✓ Coverage report generated in htmlcov/index.html$(NC)"

# ============================================================================
# Code Quality Commands
# ============================================================================

lint:
	@echo "$(BLUE)Running linters...$(NC)"
	cd backend && flake8 app --max-line-length=120 --exclude=__pycache__
	cd backend && black app --check
	@echo "$(GREEN)✓ Linting complete$(NC)"

format:
	@echo "$(BLUE)Formatting code...$(NC)"
	cd backend && black app
	cd backend && isort app
	@echo "$(GREEN)✓ Formatting complete$(NC)"

type-check:
	@echo "$(BLUE)Running type checker...$(NC)"
	cd backend && mypy app --ignore-missing-imports
	@echo "$(GREEN)✓ Type check complete$(NC)"

# ============================================================================
# Database Commands
# ============================================================================

db-shell:
	@echo "$(BLUE)Connecting to PostgreSQL...$(NC)"
	docker-compose exec postgres psql -U traceo -d traceo

db-reset:
	@echo "$(BLUE)Resetting database...$(NC)"
	docker-compose down -v
	docker-compose up -d postgres
	@echo "$(YELLOW)Waiting for database...$(NC)"
	sleep 5
	docker-compose exec backend python -c "from app.database import init_db; init_db()"
	@echo "$(GREEN)✓ Database reset$(NC)"

db-migrate:
	@echo "$(BLUE)Running migrations...$(NC)"
	docker-compose exec backend alembic upgrade head
	@echo "$(GREEN)✓ Migrations complete$(NC)"

# ============================================================================
# Documentation Commands
# ============================================================================

docs:
	@echo "$(BLUE)Documentation files:$(NC)"
	@echo "  - README.md              Overview and quick start"
	@echo "  - IMPLEMENTATION.md      Detailed implementation guide"
	@echo "  - docs/ARCHITECTURE.md   System architecture"
	@echo "  - docs/DEPLOYMENT.md     Deployment instructions"
	@echo "  - CONTRIBUTING.md        Contribution guidelines"
	@echo ""
	@echo "$(GREEN)✓ See above for documentation$(NC)"

api-docs:
	@echo "$(BLUE)Opening API documentation...$(NC)"
	@echo "Navigate to: http://localhost:8000/docs"
	@echo ""
	@echo "To use:"
	@echo "1. Run: make up"
	@echo "2. Open: http://localhost:8000/docs"
	@echo "3. Try API endpoints interactively"

# ============================================================================
# Utility Commands
# ============================================================================

clean:
	@echo "$(BLUE)Cleaning up...$(NC)"
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".DS_Store" -delete
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf build/ dist/ *.egg-info
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

translate:
	@echo "$(BLUE)Generating translations...$(NC)"
	python scripts/generate_translations.py
	@echo "$(GREEN)✓ Translations generated$(NC)"

health-check:
	@echo "$(BLUE)Checking service health...$(NC)"
	@echo ""
	@echo "$(YELLOW)Backend:$(NC)"
	@curl -s http://localhost:8000/health | python -m json.tool 2>/dev/null || echo "Backend not responding"
	@echo ""
	@echo "$(YELLOW)Frontend:$(NC)"
	@curl -s http://localhost:3000 > /dev/null && echo "Frontend is running" || echo "Frontend not responding"
	@echo ""
	@echo "$(YELLOW)Database:$(NC)"
	@docker-compose exec -T postgres pg_isready -U traceo 2>/dev/null && echo "Database is running" || echo "Database not responding"

# ============================================================================
# Default Target
# ============================================================================

.DEFAULT_GOAL := help
