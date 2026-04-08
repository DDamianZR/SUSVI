.PHONY: test test-fast dev deploy

# Variables
PYTHON = python
PYTEST = pytest
FRONTEND_DIR = urbania/frontend
BACKEND_DIR = urbania/backend

test:
	@echo "Running all tests (including Watsonx if PROD_MODE=1)..."
	cd $(BACKEND_DIR) && $(PYTEST) tests/

test-fast:
	@echo "Running fast tests with Watsonx disabled locally..."
	cd $(BACKEND_DIR) && URBANIA_PROD_MODE=0 $(PYTEST) tests/

dev:
	@echo "Starting URBANIA Platform (Backend & Frontend)..."
	@echo "Booting FastAPI (localhost:8000)..."
	cd $(BACKEND_DIR) && uvicorn main:app --reload &
	@echo "Booting Vite React App (localhost:5173)..."
	cd $(FRONTEND_DIR) && npm run dev

deploy:
	@echo "Deploying to IBM Cloud Functions..."
	cd $(BACKEND_DIR)/cloud_functions && chmod +x deploy.sh && ./deploy.sh
