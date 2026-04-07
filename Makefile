.PHONY: dev test mock install clean

dev:
	docker-compose up --build

mock:
	MOCK_MODE=true docker-compose up --build

test:
	cd backend && pytest tests/ -v

install:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

clean:
	docker-compose down
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -name "*.pyc" -delete
