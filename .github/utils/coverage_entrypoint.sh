#!/usr/bin/env bash
set -mx

# Run server with coverage as a job
gunicorn --bind "0.0.0.0:${PORT}" --log-level debug --workers 1 --worker-class dlite_entities_service.uvicorn.UvicornWorker run_with_coverage:APP &

echo "$(jobs -l)"

echo "Run time is ${RUN_TIME:-40} seconds"
sleep ${RUN_TIME:-40}

echo "stopping gunicorn"
GUNICORN_PID=$(ps -C gunicorn fch -o pid | head -n 1)
kill -HUP $GUNICORN_PID
sleep ${STOP_TIME:-3}

echo "exited $0"
