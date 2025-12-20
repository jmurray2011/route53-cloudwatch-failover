# Include environment variables from .env file
-include .env
export $(shell [ -f .env ] && sed 's/=.*//' .env || echo "")

# Define variables
ZIP_FILE=lambda_function.zip

# Default target executed when no arguments are given to make
all: deploy

# Help target
help:
	@echo "Available targets:"
	@echo "  make test    - Run unit tests with coverage"
	@echo "  make lint    - Run code quality checks"
	@echo "  make zip     - Create deployment package"
	@echo "  make deploy  - Deploy to AWS Lambda (requires .env file)"
	@echo "  make clean   - Remove deployment package and test artifacts"
	@echo ""
	@echo "Required .env file with: FUNCTION_NAME, SOURCE_FILE, AWS_PROFILE, AWS_REGION"

# Target for running tests
test:
	@echo "Running unit tests..."
	pytest

# Target for linting (all linters, non-strict for local development)
lint:
	@echo "Running code quality checks..."
	@echo "Running black..."
	black --check lambda_function.py test_lambda_function.py || true
	@echo "Running flake8..."
	flake8 lambda_function.py test_lambda_function.py --max-line-length=100 || true
	@echo "Running mypy..."
	mypy lambda_function.py || true

# Individual lint targets (strict, for CI)
lint-black:
	black --check lambda_function.py test_lambda_function.py

lint-flake8:
	flake8 lambda_function.py test_lambda_function.py --max-line-length=100

lint-mypy:
	mypy lambda_function.py

# Check if .env file exists
check-env:
	@if [ ! -f .env ]; then \
		echo "Error: .env file not found. Copy example.env to .env and configure it."; \
		exit 1; \
	fi

# Target for zipping the lambda function
zip:
	@echo "Zipping the Python script..."
	zip $(ZIP_FILE) $(SOURCE_FILE)

# Target for deploying to AWS Lambda
deploy: check-env zip
	@echo "Deploying to AWS Lambda using profile $(AWS_PROFILE) in region $(AWS_REGION)..."
	aws lambda update-function-code --function-name $(FUNCTION_NAME) --zip-file fileb://$(ZIP_FILE) --profile $(AWS_PROFILE) --region $(AWS_REGION)

# Clean up the zip file and test artifacts
clean:
	@echo "Cleaning up..."
	rm -f $(ZIP_FILE)
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf __pycache__
	rm -rf .mypy_cache
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

.PHONY: all help test lint lint-black lint-flake8 lint-mypy check-env zip deploy clean
