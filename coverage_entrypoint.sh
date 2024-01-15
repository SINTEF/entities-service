#!/usr/bin/env bash
set -ex

pip install -U coverage

UVICORN_CMD=$(which uvicorn)
if [ -z "${UVICORN_CMD}" ]; then
    echo "uvicorn not found"
    exit 1
fi

# Run uvicorn with coverage
coverage run ${UVICORN_CMD} --host 0.0.0.0 --port ${PORT} --log-level debug --no-server-header --header "Server:DLiteEntitiesService" --reload dlite_entities_service.main:APP
