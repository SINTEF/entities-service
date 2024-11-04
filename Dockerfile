FROM python:3.10 AS base

WORKDIR /app

COPY entities_service entities_service/
COPY pyproject.toml LICENSE README.md ./

# Install dependencies
RUN python -m pip install -U pip && \
  pip install -U setuptools wheel && \
  pip install -U -e .[server]

ENV PORT=80
EXPOSE ${PORT}

ENTRYPOINT [ "gunicorn", "entities_service.main:APP", "--bind=0.0.0.0:${PORT}", "--workers=1", "--worker-class=entities_service.uvicorn.UvicornWorker", ]

## DEVELOPMENT target
FROM base AS development

# Copy over the self-signed certificates for development
COPY docker_security docker_security/

# Set debug mode, since we're running in development mode
ENV ENTITIES_SERVICE_DEBUG=1

CMD [ "--log-level=debug", "--reload" ]

## PRODUCTION target
FROM base AS production

# Force debug mode to be off, since we're running in production mode
ENV ENTITIES_SERVICE_DEBUG=0
