.PHONY: build deploy delete local-api test smoke frontend-dev frontend-build frontend-deploy deploy-all

build:
	sam build

deploy: build
	sam deploy

delete:
	sam delete

local-api: build
	sam local start-api --port 3000

test:
	pytest -v

smoke:
	chmod +x scripts/smoke_test.sh
	./scripts/smoke_test.sh

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build

frontend-deploy: frontend-build
	@if [ -z "$$FRONTEND_BUCKET" ]; then echo "Set FRONTEND_BUCKET to your S3 bucket name"; exit 1; fi
	aws s3 sync frontend/dist/ s3://$$FRONTEND_BUCKET/ --delete

deploy-all: deploy frontend-deploy
