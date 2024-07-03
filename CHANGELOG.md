# Changelog

## [Unreleased](https://github.com/SINTEF/entities-service/tree/HEAD)

[Full Changelog](https://github.com/SINTEF/entities-service/compare/v0.7.0...HEAD)

# New `list` command group

Two new commands are introduced to the CLI:

## `list namespaces`

This returns a table overview of all fully qualified URL namespaces that contain entities from the service located at the value given by the environment variable `ENTITIES_SERVICE_BASE_URL`.

## `list entities`

Takes as many `NAMESPACE` arguments as desired - even zero. And will list all the entities found in those given namespaces.
If no namespace is given, the value given by the environment variable `ENTITIES_SERVICE_BASE_URL` will be used.

One can also use the option `--all-namespaces/-a` to return all entities for the core and all specific namespaces at `ENTITIES_SERVICE_BASE_URL`.

# Miscellaneous

Several DX and dependency updates have been introduced, for a full overview, please see the full changelog.

**Implemented enhancements:**

- ✨ List and report on entities in \(specific\) namespace [\#107](https://github.com/SINTEF/entities-service/issues/107)

## [v0.7.0](https://github.com/SINTEF/entities-service/tree/v0.7.0) (2024-07-02)

[Full Changelog](https://github.com/SINTEF/entities-service/compare/v0.6.0...v0.7.0)

**Implemented enhancements:**

- Separate entity URI/identity from hosting URL [\#76](https://github.com/SINTEF/entities-service/issues/76)

**Fixed bugs:**

- 🔧 Cap DLite version [\#161](https://github.com/SINTEF/entities-service/issues/161)
- 🔧 Fix lines in table output from upload summary [\#149](https://github.com/SINTEF/entities-service/issues/149)
- 🔧 Ensure the service is deployed if the dependencies are updated [\#139](https://github.com/SINTEF/entities-service/issues/139)
- 🔧 `dimensions` should always be returned [\#102](https://github.com/SINTEF/entities-service/issues/102)

**Closed issues:**

- 📄 Document the CLI API [\#148](https://github.com/SINTEF/entities-service/issues/148)

**Merged pull requests:**

- Support latest DLite version \(v0.5.16\) [\#162](https://github.com/SINTEF/entities-service/pull/162) ([CasperWA](https://github.com/CasperWA))
- \[pre-commit.ci\] pre-commit autoupdate [\#159](https://github.com/SINTEF/entities-service/pull/159) ([pre-commit-ci[bot]](https://github.com/apps/pre-commit-ci))
- \[pre-commit.ci\] pre-commit autoupdate [\#157](https://github.com/SINTEF/entities-service/pull/157) ([pre-commit-ci[bot]](https://github.com/apps/pre-commit-ci))
- \[pre-commit.ci\] pre-commit autoupdate [\#155](https://github.com/SINTEF/entities-service/pull/155) ([pre-commit-ci[bot]](https://github.com/apps/pre-commit-ci))
- Ensure `last_namespace` is updated iteratively [\#151](https://github.com/SINTEF/entities-service/pull/151) ([CasperWA](https://github.com/CasperWA))
- Add pyproject.toml to service changes file checklist [\#150](https://github.com/SINTEF/entities-service/pull/150) ([CasperWA](https://github.com/CasperWA))
- \[pre-commit.ci\] pre-commit autoupdate [\#147](https://github.com/SINTEF/entities-service/pull/147) ([pre-commit-ci[bot]](https://github.com/apps/pre-commit-ci))
- Add CLI documentation [\#114](https://github.com/SINTEF/entities-service/pull/114) ([CasperWA](https://github.com/CasperWA))
- List entities in namespace\(s\) [\#111](https://github.com/SINTEF/entities-service/pull/111) ([CasperWA](https://github.com/CasperWA))

## [v0.6.0](https://github.com/SINTEF/entities-service/tree/v0.6.0) (2024-05-08)

[Full Changelog](https://github.com/SINTEF/entities-service/compare/v0.5.0...v0.6.0)

# Support `identity` and ensure `dimensions` is present

`identity` is now allowed as an alias for `uri`. This is in accord with regular SOFT schemas.

The `dimensions` key is now always returned when retrieving an entity, even if empty. This is done mainly to support DLite usage, since DLite cannot handle entities that do not explicitly define the `dimensions` key, even though it may be empty.

# pre-commit.ci

The DX has been optimized by using [pre-commit.ci](https://pre-commit.ci) for running pre-commit hooks on a PR as well as autoupgrading the hooks weekly as part of the repository's CI/CD.

**Merged pull requests:**

- \[pre-commit.ci\] pre-commit autoupdate [\#144](https://github.com/SINTEF/entities-service/pull/144) ([pre-commit-ci[bot]](https://github.com/apps/pre-commit-ci))
- \[pre-commit.ci\] pre-commit autoupdate [\#141](https://github.com/SINTEF/entities-service/pull/141) ([pre-commit-ci[bot]](https://github.com/apps/pre-commit-ci))
- Allow `identity`, ensure `dimensions` is returned, & use pre-commit.ci [\#103](https://github.com/SINTEF/entities-service/pull/103) ([CasperWA](https://github.com/CasperWA))

## [v0.5.0](https://github.com/SINTEF/entities-service/tree/v0.5.0) (2024-04-26)

[Full Changelog](https://github.com/SINTEF/entities-service/compare/v0.4.0...v0.5.0)

# Use the CLI in CI/CD

With the latest updates to the `entities-service` CLI it can be used as intended in CI/CD workflows.

To make this happen, this release further upgrades the CLI, mainly by deprecating the `--file/-f` and `--dir/-d` inputs for the `upload` and `validate` commands in favor of a `SOURCE...` argument, i.e., one can supply (relative or absolute) paths to files and directories multiple times to the commands, separating them by a space (or wrapping them in quotation marks (either `"` or `'` will work).

In addition, this new `SOURCE...` argument is utilized in two cases:
- One can supply the arguments via `stdin`.
- The `validate` command has been wrapped as a [pre-commit](https://pre-commit.com) hook.

The `stdin` possibility allows one to do something like:

```console
git diff --name-only | entities-service validate -
```

This will supply the `validate` command with a list of files that are different between the current `git` working directory and the previous commit.

## pre-commit hook `validate-entities`

When using the hook, one should focus in the files it runs on via the `files` hook argument. One _must_ also supply the argument `additional_dependencies` with the value `'.[cli]'` (note, this argument expects a list, so this value should be one of the  values in that list).

The hook will automatically run on all implemented formats (currently JSON and YAML/YML).

The hook will automatically use the `--verbose` flag, should there be any content differences between the local and externally existing counterparts.

**Implemented enhancements:**

- ✨ Support piping in SOURCE's \(filepaths and directories\) [\#130](https://github.com/SINTEF/entities-service/issues/130)
- ✨ New option `--strict` for the `validate` command [\#129](https://github.com/SINTEF/entities-service/issues/129)
- ✨ Run some CLI commands as pre-commit hooks [\#122](https://github.com/SINTEF/entities-service/issues/122)

**Closed issues:**

- Only deploy service if changes in service is detected [\#92](https://github.com/SINTEF/entities-service/issues/92)

**Merged pull requests:**

- Update README with pre-commit and CLI info [\#134](https://github.com/SINTEF/entities-service/pull/134) ([CasperWA](https://github.com/CasperWA))
- Add `--strict` option to CLI [\#132](https://github.com/SINTEF/entities-service/pull/132) ([CasperWA](https://github.com/CasperWA))
- Support using stdin as input for CLI [\#131](https://github.com/SINTEF/entities-service/pull/131) ([CasperWA](https://github.com/CasperWA))
- Only deploy service to onto-ns.com if relevant changes detected [\#124](https://github.com/SINTEF/entities-service/pull/124) ([CasperWA](https://github.com/CasperWA))

## [v0.4.0](https://github.com/SINTEF/entities-service/tree/v0.4.0) (2024-04-23)

[Full Changelog](https://github.com/SINTEF/entities-service/compare/v0.3.0...v0.4.0)

## New `validate` CLI command

A new CLI command (`validate`) has been added to make it possible to validate entities.
This is convenient both as a split of the bloated `upload` command implementation, but also as a separate functionality for data documentation repositories to ensure any changes to entities will still result in valid entities.

Furthermore, a new `--auto-confirm/-y` option has been added to the `upload` command as an extension on the `--quiet/-q` option. It will still ensure print statements occur, but will use defaults and "Yes" responses whenever it is needed.

**Implemented enhancements:**

- ✨ Add an option to the `upload` command to auto-confirm the summary [\#119](https://github.com/SINTEF/entities-service/issues/119)
- ✨ Add a new `validate` command [\#118](https://github.com/SINTEF/entities-service/issues/118)

**Merged pull requests:**

- New `--auto-confirm/-y` option for `upload` cmd [\#121](https://github.com/SINTEF/entities-service/pull/121) ([CasperWA](https://github.com/CasperWA))
- Add a new 'validate' CLI command [\#120](https://github.com/SINTEF/entities-service/pull/120) ([CasperWA](https://github.com/CasperWA))

## [v0.3.0](https://github.com/SINTEF/entities-service/tree/v0.3.0) (2024-04-09)

[Full Changelog](https://github.com/SINTEF/entities-service/compare/v0.2.0...v0.3.0)

## CI/CD-friendly CLI

The CLI now supports setting an access token to upload entities - this avoids the need for manual interaction when authenticating using GitLab. The access token should preferably be case-specific and created as a group access token (see the [GitLab documentation](https://docs.gitlab.com/ee/user/group/settings/group_access_tokens.html) for more information about group access tokens).

> Note, the minimum access level for the token should still be `Developer` for it to be allowed to create entities.
> Beware that this minimum access level may change in the future.
# Support specific namespaced URIs

Support specific namespaced URIs according to #7. If one has write rights for the entity backend, by setting the `namespace` and/or `uri` value in the entity files, they will use the relevant namespace, either the core namespace or a specific namespace.

## UX/DX updates

Otherwise, the code has had some clean up related to entity model definitions, separating out the SOFT flavorings. Some fixes have been implemented after first tests have been run "in production".

**Implemented enhancements:**

- 🔐 Support supplying access token to upload [\#108](https://github.com/SINTEF/entities-service/issues/108)

**Fixed bugs:**

- An access token is not tested properly in the service [\#112](https://github.com/SINTEF/entities-service/issues/112)

**Merged pull requests:**

- Fix using access token [\#113](https://github.com/SINTEF/entities-service/pull/113) ([CasperWA](https://github.com/CasperWA))
- Add ENTITIES\_SERVICE\_ACCESS\_TOKEN env var [\#110](https://github.com/SINTEF/entities-service/pull/110) ([CasperWA](https://github.com/CasperWA))

## [v0.2.0](https://github.com/SINTEF/entities-service/tree/v0.2.0) (2024-03-22)

[Full Changelog](https://github.com/SINTEF/entities-service/compare/v0.1.0...v0.2.0)

# Support specific namespaced URIs

Support specific namespaced URIs according to #7. If one has write rights for the entity backend, by setting the `namespace` and/or `uri` value in the entity files, they will use the relevant namespace, either the core namespace or a specific namespace.

## UX/DX updates

Otherwise, the code has had some clean up related to entity model definitions, separating out the SOFT flavorings. Some fixes have been implemented after first tests have been run "in production".

**Fixed bugs:**

- The pydantic model for `GitLabUserInfo` is too strict [\#83](https://github.com/SINTEF/entities-service/issues/83)
- The cache dir is not being created automatically [\#82](https://github.com/SINTEF/entities-service/issues/82)

**Closed issues:**

- Loosen name regex for retrieving entities [\#90](https://github.com/SINTEF/entities-service/issues/90)
- Minimize code repeats in SOFT models [\#64](https://github.com/SINTEF/entities-service/issues/64)
- Test with different "versions" of entity schemas [\#5](https://github.com/SINTEF/entities-service/issues/5)

**Merged pull requests:**

- Support specific namespaces [\#101](https://github.com/SINTEF/entities-service/pull/101) ([CasperWA](https://github.com/CasperWA))
- Unify entity version and name validation [\#91](https://github.com/SINTEF/entities-service/pull/91) ([CasperWA](https://github.com/CasperWA))
- Clean up authorization models [\#88](https://github.com/SINTEF/entities-service/pull/88) ([CasperWA](https://github.com/CasperWA))
- Try to create cache directory on each CLI call [\#87](https://github.com/SINTEF/entities-service/pull/87) ([CasperWA](https://github.com/CasperWA))
- Separate out entity models in SOFT and DLite [\#74](https://github.com/SINTEF/entities-service/pull/74) ([CasperWA](https://github.com/CasperWA))

## [v0.1.0](https://github.com/SINTEF/entities-service/tree/v0.1.0) (2024-01-31)

[Full Changelog](https://github.com/SINTEF/entities-service/compare/v0.0.1...v0.1.0)

This is the first "proper" release (after v0.0.1).

It introduces several steps up compared to a bare-bones REST API service that started as a way to return the entities from the URI/URL they have defined. Specifically on the onto-ns.com domain under the `/meta` path.

The main upgrade revolves around the CLI, implemented to facilitate uploading entities.
It does so by connecting to the REST API service, authenticating via SINTEF's GitLab OAuth2 flow.

A PyPI release is not planned yet. To install this package run (in a virtual environment):

```console
pip install "entities-service[cli] @ git+https://github.com/SINTEF/entities-service.git"
```

Then run:

```console
entities-service --help
```

To learn more about the CLI.

**Implemented enhancements:**

- Add a release workflow [\#68](https://github.com/SINTEF/entities-service/issues/68)
- Change target for the CLI upload [\#63](https://github.com/SINTEF/entities-service/issues/63)
- Integrate current docker tests into a local pytest runnable environment [\#53](https://github.com/SINTEF/entities-service/issues/53)
- Update to ruff [\#51](https://github.com/SINTEF/entities-service/issues/51)
- Add dependency CI workflows [\#13](https://github.com/SINTEF/entities-service/issues/13)
- Help script for uploading entities [\#12](https://github.com/SINTEF/entities-service/issues/12)

**Fixed bugs:**

- Onto-ns expects entity in the "wrong" format [\#38](https://github.com/SINTEF/entities-service/issues/38)
- Deployment to onto-ns failing due to mishandling URL to MongoDB [\#31](https://github.com/SINTEF/entities-service/issues/31)

**Closed issues:**

- Minimize repo name [\#62](https://github.com/SINTEF/entities-service/issues/62)
- Move repository to SINTEF organization [\#10](https://github.com/SINTEF/entities-service/issues/10)
- Implement CD workflow for deploying updates on onto-ns.com [\#6](https://github.com/SINTEF/entities-service/issues/6)
- Be reasonable regarding version and name regex [\#4](https://github.com/SINTEF/entities-service/issues/4)

**Merged pull requests:**

- Use the more concise 'Entities Service' name throughout [\#70](https://github.com/SINTEF/entities-service/pull/70) ([CasperWA](https://github.com/CasperWA))
- Add a release workflow [\#69](https://github.com/SINTEF/entities-service/pull/69) ([CasperWA](https://github.com/CasperWA))
- New `POST` create entity endpoint - also authentication [\#67](https://github.com/SINTEF/entities-service/pull/67) ([CasperWA](https://github.com/CasperWA))
- Minimal CLI for uploading functionality [\#55](https://github.com/SINTEF/entities-service/pull/55) ([CasperWA](https://github.com/CasperWA))
- Setup unit tests using `pytest` [\#54](https://github.com/SINTEF/entities-service/pull/54) ([CasperWA](https://github.com/CasperWA))
- Update dev tools [\#52](https://github.com/SINTEF/entities-service/pull/52) ([CasperWA](https://github.com/CasperWA))
- Split pydantic models to include SOFT5 as well [\#40](https://github.com/SINTEF/entities-service/pull/40) ([CasperWA](https://github.com/CasperWA))
- Use custom MongoDsn pydantic URL type [\#32](https://github.com/SINTEF/entities-service/pull/32) ([CasperWA](https://github.com/CasperWA))
- Add CI/CD workflows [\#14](https://github.com/SINTEF/entities-service/pull/14) ([CasperWA](https://github.com/CasperWA))
- Add deployment workflow [\#11](https://github.com/SINTEF/entities-service/pull/11) ([CasperWA](https://github.com/CasperWA))
- Enable custom port and user for mongodb + fixed typo in readme [\#9](https://github.com/SINTEF/entities-service/pull/9) ([jesper-friis](https://github.com/jesper-friis))
- Be more specific about the regex for version and name [\#8](https://github.com/SINTEF/entities-service/pull/8) ([CasperWA](https://github.com/CasperWA))
- Include a bit of logging [\#3](https://github.com/SINTEF/entities-service/pull/3) ([CasperWA](https://github.com/CasperWA))
- Add uvicorn worker [\#2](https://github.com/SINTEF/entities-service/pull/2) ([CasperWA](https://github.com/CasperWA))
- Fix new Docker CI test [\#1](https://github.com/SINTEF/entities-service/pull/1) ([CasperWA](https://github.com/CasperWA))

## [v0.0.1](https://github.com/SINTEF/entities-service/tree/v0.0.1) (2023-03-30)

[Full Changelog](https://github.com/SINTEF/entities-service/compare/aabe29f4aa4b20d4c2c3e1b46d0ad20467f6fbfb...v0.0.1)



\* *This Changelog was automatically generated by [github_changelog_generator](https://github.com/github-changelog-generator/github-changelog-generator)*
