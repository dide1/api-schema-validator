"""AWS Lambda entrypoint. Deploy with SAM; handler is ``handler.handler``."""

from mangum import Mangum

from app.main import app as fastapi_app
import app.config

if app.config.AUTH_ENABLED:
    from app.services.template_service import template_service

    template_service.seed_bundled_templates()

handler = Mangum(fastapi_app, lifespan="off")
