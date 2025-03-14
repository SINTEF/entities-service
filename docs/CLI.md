# `entities-service`

Entities Service utility CLI

**Usage**:

```console
$ entities-service [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--version`: Show version and exit.
* `--dotenv-config FILE`: Use the .env file at the given location for the current command. By default it will point to the .env file in the current directory.  [default: .env]
* `--install-completion`: Install completion for the current shell.
* `--show-completion`: Show completion for the current shell, to copy it or customize the installation.
* `--help`: Show this message and exit.

**Commands**:

* `login`: Login to the entities service.
* `upload`: Upload (local) entities to a remote location.
* `validate`: Validate (local) entities.
* `config`: Manage configuration options.
* `list`: List resources.

## `entities-service login`

Login to the entities service.

**Usage**:

```console
$ entities-service login [OPTIONS]
```

**Options**:

* `-q, -s, -y, --quiet, --silent`: Do not print anything on success and do not ask for confirmation.
* `--help`: Show this message and exit.

## `entities-service upload`

Upload (local) entities to a remote location.

**Usage**:

```console
$ entities-service upload [OPTIONS] [SOURCE]...
```

**Arguments**:

* `[SOURCE]...`: Path to file or directory with one or more entities.

**Options**:

* `--format [json|yaml|yml]`: Format of entity file(s).  [default: json]
* `--fail-fast`: Stop uploading entities on the first error during file validation.
* `-q, -s, --quiet, --silent`: Do not print anything on success and do not ask for confirmation. IMPORTANT, for content conflicts the defaults will be chosen.
* `-y, --auto-confirm`: Automatically agree to any confirmations and use defaults for content conflicts. This differs from --quiet in that it will still print information.
* `--strict`: Strict validation of entities. This means the command will fail during the validation process, if an external entity already exists and the two entities are not equal. This option is only relevant if &#x27;--no-external-calls&#x27; is not provided. If both &#x27;--no-external-calls&#x27; and this options is provided, an error will be emitted.
* `--help`: Show this message and exit.

## `entities-service validate`

Validate (local) entities.

**Usage**:

```console
$ entities-service validate [OPTIONS] [SOURCE]...
```

**Arguments**:

* `[SOURCE]...`: Path to file or directory with one or more entities.

**Options**:

* `--format [json|yaml|yml]`: Format of entity file(s).  [default: json]
* `--fail-fast`: Stop validating entities on the first discovered error.
* `-q, -s, -y, --quiet, --silent`: Do not print anything on success.
* `--no-external-calls`: Do not make any external calls to validate the entities. This includes mainly comparing local entities with their remote counterparts.
* `-v, --verbose`: Print the differences between the external and local entities (if any).
* `--strict`: Strict validation of entities. This means validation will fail if an external entity already exists and the two entities are not equal. This option is only relevant if &#x27;--no-external-calls&#x27; is not provided. If both &#x27;--no-external-calls&#x27; and this options is provided, an error will be emitted.
* `--help`: Show this message and exit.

## `entities-service config`

Manage configuration options.

**Usage**:

```console
$ entities-service config [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--version`: Show version and exit.
* `--dotenv-config FILE`: Use the .env file at the given location for the current command. By default it will point to the .env file in the current directory.  [default: .env]
* `--help`: Show this message and exit.

**Commands**:

* `set`: Set a configuration option.
* `show`: Show the current configuration.
* `unset`: Unset a single configuration option.
* `unset-all`: Unset all configuration options.

### `entities-service config set`

Set a configuration option.

**Usage**:

```console
$ entities-service config set [OPTIONS] KEY:{access_token|backend|base_url|ca_file|debug|mongo_collection|mongo_db|mongo_password|mongo_uri|mongo_user|oauth2_provider|oauth2_provider_base_url|roles_group|x509_certificate_file} [VALUE]
```

**Arguments**:

* `KEY:{access_token|backend|base_url|ca_file|debug|mongo_collection|mongo_db|mongo_password|mongo_uri|mongo_user|oauth2_provider|oauth2_provider_base_url|roles_group|x509_certificate_file}`: Configuration option to set. These can also be set as an environment variable by prefixing with &#x27;ENTITIES_SERVICE_&#x27;.  [required]
* `[VALUE]`: Value to set. This will be prompted for if not provided.

**Options**:

* `--help`: Show this message and exit.

### `entities-service config show`

Show the current configuration.

**Usage**:

```console
$ entities-service config show [OPTIONS]
```

**Options**:

* `--reveal-sensitive`: Reveal sensitive values. (DANGEROUS! Use with caution.)
* `--help`: Show this message and exit.

### `entities-service config unset`

Unset a single configuration option.

**Usage**:

```console
$ entities-service config unset [OPTIONS] KEY:{access_token|backend|base_url|ca_file|debug|mongo_collection|mongo_db|mongo_password|mongo_uri|mongo_user|oauth2_provider|oauth2_provider_base_url|roles_group|x509_certificate_file}
```

**Arguments**:

* `KEY:{access_token|backend|base_url|ca_file|debug|mongo_collection|mongo_db|mongo_password|mongo_uri|mongo_user|oauth2_provider|oauth2_provider_base_url|roles_group|x509_certificate_file}`: Configuration option to unset.  [required]

**Options**:

* `--help`: Show this message and exit.

### `entities-service config unset-all`

Unset all configuration options.

**Usage**:

```console
$ entities-service config unset-all [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.

## `entities-service list`

List resources.

**Usage**:

```console
$ entities-service list [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `entities`: List entities from the entities service.
* `namespaces`: List namespaces from the entities service.

### `entities-service list entities`

List entities from the entities service.

**Usage**:

```console
$ entities-service list entities [OPTIONS] [NAMESPACE]...
```

**Arguments**:

* `[NAMESPACE]...`: Namespace(s) to list entities from. Defaults to the core namespace. If the namespace is a URL, the specific namespace will be extracted.

**Options**:

* `-a, --all`: List entities from all namespaces.
* `--help`: Show this message and exit.

### `entities-service list namespaces`

List namespaces from the entities service.

**Usage**:

```console
$ entities-service list namespaces [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.
