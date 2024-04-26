# Entities Service

> REST API service for serving entities

This is a FastAPI-based REST API service running on onto-ns.com.
It's purpose is to serve entities from an underlying database.

Other than the REST API service, the repository also contains a CLI for validating and uploading entities to the service, as well as create and manipulate the service' configuration file.
See the [CLI documentation](#cli) for more information.

The repository also contains a [pre-commit](https://pre-commit.com/) hook `validate-entities`, which may be used externally to validate entities before committing them a repository.
See the [pre-commit hook documentation](#pre-commit-hook-validate-entities) for more information.

## Install the service

First, download and install the Python package from GitHub:

```shell
# Download (git clone)
git clone https://github.com/SINTEF/entities-service.git
cd entities-service

# Install (using pip)
python -m pip install -U pip
pip install -U -e .
```

## Run the service

The service requires a MongoDB server to be running, and the service needs to be able to connect to it.
The service also requires a valid X.509 certificate, in order to connect to the MongoDB server.

The MongoDB server could be MongoDB Atlas, a local MongoDB server, or a Docker container running MongoDB.

### Using the local environment and MongoDB Atlas

First, create a MongoDB Atlas cluster, and a user with read-only access to the `entities` database.

Set the necessary environment variables:

```shell
ENTITIES_SERVICE_MONGO_URI=<your MongoDB Atlas URI>
ENTITIES_SERVICE_X509_CERTIFICATE_FILE=<your X.509 certificate file>
ENTITIES_SERVICE_MONGO_USER=<your MongoDB Atlas user with read-only access (default: 'guest')>
ENTITIES_SERVICE_MONGO_PASSWORD=<your MongoDB Atlas user's password with read-only access (default: 'guest')>
```

Run the service:

```shell
uvicorn entities_service.main:APP --host localhost --port 8000 --no-server-header --header "Server:EntitiesService"
```

Finally, go to [localhost:8000/docs](http://localhost:8000/docs) and try out retrieving an entity.

`--log-level debug` can be added to the `uvicorn` command to get more verbose logging.
`--reload` can be added to the `uvicorn` command to enable auto-reloading of the service when any files are changed.

Note, the environment variables can be set in a `.env` file, see the section on [using a file for environment variables](#using-a-file-for-environment-variables).

### Using Docker and a local MongoDB server

First, we need to create self-signed certificates for the service to use.
This is done by running the following command:

```shell
mkdir docker_security
cd docker_security
../.github/docker_init/setup_mongo_security.sh
```

Note, this is only possible with `openssl` installed on your system.
And the OS on the system being Linux/Unix-based.

For development, start a local MongoDB server, e.g., through another Docker image:

```shell
docker run --rm -d \
  --env "IN_DOCKER=true" \
  --env "HOST_USER=${USER}" \
  --env "MONGO_INITDB_ROOT_USERNAME=root" \
  --env "MONGO_INITDB_ROOT_PASSWORD=root" \
  --name "mongodb" \
  -p "27017:27017" \
  -v "${PWD}/.github/docker_init/create_x509_user.js:/docker-entrypoint-initdb.d/0_create_x509_user.js" \
  -v "${PWD}/docker_security:/mongo_tls" \
  mongo:7 \
  --tlsMode allowTLS --tlsCertificateKeyFile /mongo_tls/test-server1.pem --tlsCAFile /mongo_tls/
```

Then build and run the Entities Service Docker image:

```shell
docker build --pull -t entities-service --target development .
docker run --rm -d \
  --env "ENTITIES_SERVICE_MONGO_URI=mongodb://localhost:27017" \
  --env "ENTITIES_SERVICE_X509_CERTIFICATE_FILE=docker_security/test-client.pem" \
  --env "ENTITIES_SERVICE_CA_FILE=docker_security/test-ca.pem" \
  --name "entities-service" \
  -u "${id -ur}:${id -gr}" \
  -p "8000:80" \
  entities-service
```

Now, fill up the MongoDB with valid entities at the `entities_service` database in the `entities` collection.

Then go to [localhost:8000/docs](http://localhost:8000/docs) and try out retrieving an entity.

---

For production, use a public MongoDB, and follow the same instructions above for building and running the Entities Service Docker image, but exchange the `--target` value with `production`, put in the proper value for the `ENTITIES_SERVICE_MONGO_URI` and `ENTITIES_SERVICE_X509_CERTIFICATE_FILE` environment values, possibly add the `ENTITIES_SERVICE_MONGO_USER`, `ENTITIES_SERVICE_MONGO_PASSWORD`, and `ENTITIES_SERVICE_CA_FILE` environment variables as well, if needed.

### Using Docker Compose

Run the following commands:

```shell
docker compose pull
docker compose --env-file=.env up --build
```

By default the `development` target will be built, to change this, set the `ENTITIES_SERVICE_DOCKER_TARGET` environment variable accordingly, e.g.:

```shell
ENTITIES_SERVICE_DOCKER_TARGET=production docker compose --env-file=.env up --build
```

Furthermore, the used `localhost` port can be changed via the `PORT` environment variable.

The `--env-file` argument is optional, but if used, it should point to a file containing the environment variables needed by the service.
See the section on [using a file for environment variables](#using-a-file-for-environment-variables) for more information.

### Using a file for environment variables

The service supports a "dot-env" file, i.e., a `.env` file with a list of (secret) environment variables.

In order to use this, create a new file named `.env`.
This file will never be committed if you choose to `git commit` any files, as it has been hardcoded into the `.gitignore` file.

Fill up the `.env` file with (secret) environment variables.

For using it locally, no changes are needed, as the service will automatically check for a `.env` file and load it in, using it to set the service app configuration.

For using it with Docker, use the `--env-file .env` argument when calling `docker run` or `docker compose up`.

## CLI

The CLI is a command-line interface for interacting with the Entities Service.
It can be used to validate and upload entities to the service, as well as create and manipulate the service' configuration file.

To see the available commands and options, run:

```shell
entities-service --help
```

## pre-commit hook `validate-entities`

The `validate-entities` [pre-commit](https://pre-commit.com) hook runs the CLI command `entities-service validate` on all files that are about to be committed.
This is to ensure that all entities are valid before committing them to the repository.

By default it runs with the `--verbose` flag, which will print out detailed differences if an entity already exists externally and differs in its content.
Furthermore, it will run such that all supported file formats (currently JSON and YAML/YML) will be validated.

**Important**: Add the `.[cli]` entry to the `additional_dependencies` argument.

It is also advisable to focus in which directories or files the hook should run for, by adding the `files` argument.

Here is an example of how to add the `validate-entities` pre-commit hook to your `.pre-commit-config.yaml` file, given a repository that contains entities in the `entities` directory in the root of the repository:

```yaml
repos:
# ...
- repo: https://github.com/SINTEF/entities-service
  rev: v0.4.0
  hooks:
  - id: validate-entities
    additional_dependencies: [".[cli]"]
    files: ^entities/.*\.(json|yaml|yml)$
```

This will run for all JSON, YAML, and YML files in the `entities` directory and its subdirectories.

Note, you can add the `--no-external-calls` argument if you wish to not make external calls to the Entities Service when validating entities.
This is useful when running the pre-commit hook in an environment where the Entities Service is not available, or when you wish to only validate the entities locally.

```yaml
# ...
    args: ['--no-external-calls']
# ...
```

## Testing

The repository code is tested using `pytest`.
For the service, it can be tested against a local MongoDB server and Entities Service instance or against a mock MongoDB server and Entities Service instance utilizing [Starlette's TestClient](https://fastapi.tiangolo.com/reference/testclient/#test-client-testclient).

To run the tests, first install the test dependencies:

```shell
pip install -U -e .[testing]
```

Then run the tests (for mock MongoDB ([`mongomock`](https://github.com/mongomock/mongomock)) and Entities Service):

```shell
pytest
```

To run the tests against a live backend, you can pull, build, and run the [Docker Compose file](docker-compose.yml):

```shell
docker compose pull
docker compose build
```

Before running the services the self-signed certificates need to be created.
See the section on [using Docker and a local MongoDB server](#using-docker-and-a-local-mongodb-server) for more information.

Then run (up) the Docker Compose file and subsequently the tests:

```shell
docker compose up -d
pytest --live-backend
```

Remember to set the `ENTITIES_SERVICE_X509_CERTIFICATE_FILE` and `ENTITIES_SERVICE_CA_FILE` environment variables to `docker_security/test-server1.pem` and `docker_security/test-ca.pem`, respectively.
Note, these environment variables are already specified in the `docker-compose.yml` file, however, one should still check that they are set correctly.

### Test uploading entities using the CLI

To test uploading entities using the CLI, one must note that validation of the entities happens twice: First by the CLI, and then by the service.
The validation that is most tricky when testing locally is the namespace validation, as the service will validate the namespace against the `ENTITIES_SERVICE_BASE_URL` environment variable set when starting the service, which defaults to `http://onto-ns.com/meta`.
However, if using this namespace in the CLI, the CLI will connect to the publicly running service at `http://onto-ns.com/meta`, which will not work when testing locally.

So to make all this work together, one should start the service with the `ENTITIES_SERVICE_BASE_URL` environment variable set to `http://localhost:8000` (which is done through the locally available environment variable `ENTITIES_SERVICE_HOST`), and then use the CLI to upload entities to the service running at `http://localhost:8000`.

In practice, this will look like this:

```shell
# Set the relevant environment variables
export ENTITIES_SERVICE_BASE_URL=http://localhost:8000
export ENTITIES_SERVICE_HOST=${ENTITIES_SERVICE_BASE_URL}

# Start the service
docker compose up -d

# Upload entities using the CLI
entities-service upload my_entities.yaml --format=yaml
```

The `my_entities.yaml` file should contain one or more entities with `uri` values of the form `http://localhost:8000/...`.

### Extra pytest markers

There are some custom pytest markers:

- `skip_if_live_backend`: skips the test if the `--live-backend` flag is set.
  Add this marker to tests that should not be run against a live backend.
  Either because they are not relevant for a live backend, or because they currently impossible to replicate within a live backend.

  A reason can be specified as an argument to the marker, e.g.:

  ```python
  @pytest.mark.skip_if_live_backend(reason="Cannot force an HTTP error")
  def test_something():
      ...
  ```

  **Availability**: This marker is available for all tests.

- `skip_if_not_live_backend`: skips the test if the `--live-backend` flag is **not** set.
  Add this marker to tests that should only be run against a live backend.
  Mainly due to the fact that the mock backend does not support the test.

  A reason can be specified as an argument to the marker, e.g.:

  ```python
  @pytest.mark.skip_if_not_live_backend(reason="Indexing is not supported by mongomock")
  def test_something():
      ...
  ```

  **Availability**: This marker is available for all tests.

### Extra pytest fixtures

There is one fixture that may be difficult to locate, this is the `parameterized_entity` fixture.
It can be invoked to automatically parameterize a test, iterating over all the valid entities that exist in the [`valid_entities.yaml`](tests/static/valid_entities.yaml) static test file.
It will return one of these entities as a parsed dictionary for each iteration, i.e., within each test.

The fixture is available for all tests.

## Licensing & copyright

All files in this repository are [MIT licensed](LICENSE).  
Copyright by [Casper Welzel Andersen](https://github.com/CasperWA), [SINTEF](https://www.sintef.no).

## Acknowledgements

This project is made possible by funding from:

- MEDIATE (2022-2025) that receives funding from the RCN, Norway, FNR, Luxembourg, and SMWK, Germany via the M-ERA.NET programme, project9557.
  M-ERA.NET 2 and M-ERA.NET 3 have received funding from the European Union’s Horizon 2020 research and innovation programme under grant agreements No 685451 and No 958174.
- [MatCHMaker](https://he-matchmaker.eu) (2022-2026) that receives funding from the European Union’s Horizon Europe research and innovation programme under grant agreement No 101091687.
