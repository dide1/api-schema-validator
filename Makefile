.PHONY: build deploy delete local-api test smoke frontend-dev frontend-build frontend-deploy sdk-build sdk-deploy deploy-all

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

sdk-build:
	cd java-sdk && mvn package -q -DskipTests

sdk-deploy: sdk-build
	@if [ -z "$$SDK_BUCKET" ]; then \
		SDK_BUCKET=$$(aws cloudformation describe-stacks --stack-name api-schema-validator \
			--query "Stacks[0].Outputs[?OutputKey=='SdkBucketName'].OutputValue" \
			--output text 2>/dev/null); \
	fi; \
	if [ -z "$$SDK_BUCKET" ]; then echo "Could not resolve SDK_BUCKET"; exit 1; fi; \
	aws s3 cp java-sdk/target/schema-validator-sdk-1.0.0.jar \
		s3://$$SDK_BUCKET/schema-validator-sdk-1.0.0.jar --acl public-read; \
	echo "SDK published to s3://$$SDK_BUCKET/schema-validator-sdk-1.0.0.jar"

deploy-all: deploy frontend-deploy sdk-deploy
