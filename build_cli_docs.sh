#!/usr/bin/env bash

{
    typer --version > /dev/null 2>&1
} || {
    echo -e "\n❌ 'typer' is not installed." &&
    echo -e "Please install it and the 'entities-service' CLI using:\n\n  pip install .[cli]\n" &&
    exit 1
}

DOCS_PATH="docs/CLI.md"

if [ ! -f ${DOCS_PATH} ]; then
    echo "CLI documentation file not found at ${DOCS_PATH}."
    exit 1
fi

rm /tmp/CLI.md 2> /dev/null

TIMEOUT_EXECUTION_SECONDS=5
SECONDS=0

# Generate CLI documentation
typer entities_service.cli.main utils docs --output /tmp/CLI.md > /dev/null
until grep -q "# \`entities-service\`" /tmp/CLI.md || [ "$SECONDS" -gt "${TIMEOUT_EXECUTION_SECONDS}" ]; do
    typer entities_service.cli.main utils docs --output /tmp/CLI.md > /dev/null
done

if [ "$SECONDS" -gt "${TIMEOUT_EXECUTION_SECONDS}" ]; then
    echo "❌ Timeout while generating CLI documentation."
    exit 1
fi

diff --suppress-common-lines /tmp/CLI.md ${DOCS_PATH} > /dev/null 2>&1

ERROR_CODE=$?

if [ ${ERROR_CODE} -eq 2 ]; then
    echo "❌ diff encountered an error."
    exit 2
elif [ ${ERROR_CODE} -eq 1 ]; then
    echo "✨ CLI documentation will be updated."
    echo "Diff:"
    diff --suppress-common-lines --color /tmp/CLI.md ${DOCS_PATH}
    mv -f /tmp/CLI.md ${DOCS_PATH}
    echo -e "\nNow commit the changes to the documentation file:\n\n  git add ${DOCS_PATH}\n  git commit -m 'Update CLI documentation'\n"
elif [ ${ERROR_CODE} -eq 0 ]; then
    echo "👌 CLI documentation is up-to-date."
else
    echo "❌ Unknown error."
    exit 3
fi
