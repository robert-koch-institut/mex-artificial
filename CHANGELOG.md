# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- add helper to generate extracted items along with an associated rule-set
- add helper to generate standalone rule-sets
- add helpers to artificial items as infinite streams or fixed-length lists

### Changes

- updated template to https://github.com/robert-koch-institut/mex-template/commit/a67c71
- updated template to https://github.com/robert-koch-institut/mex-template/commit/ef0348
- updated template to https://github.com/robert-koch-institut/mex-template/commit/6009e2
- updated template to https://github.com/robert-koch-institut/mex-template/commit/3c389d
- BREAKING: change `generate_*` helper functions to infinite generators
- BREAKING: change merged item generation to use extracted and rule items
- change reference generation so that items can be ingested in generated order
- improve CLI with progress bar and progressive generation/file-writing
- update mex-common to 1.9

### Deprecated

### Removed

### Fixed

### Security

## [1.1.0] - 2025-10-22

### Changes

- update mex-common to 1.7
- change email generation to derive generation from mex-model examples

## [1.0.0] - 2025-08-21

### Changes

- update mex-common to 1.0
- bump cookiecutter template to b18156

## [0.5.4] - 2025-07-28

### Changes

- update mex-common to 0.65

## [0.5.3] - 2025-07-24

### Changes

- update mex-common to 0.64
- bump cookiecutter template to e886ec

## [0.5.2] - 2025-07-17

### Changes

- update mex-common to 0.63

## [0.5.1] - 2025-07-07

### Changes

- update mex-common to 0.62.1

## [0.5.0] - 2025-06-17

### Changes

- use mex-common from pypi

## [0.4.5] - 2025-06-17

### Fixed

- resolve pypi issues

## [0.4.4] - 2025-06-17

### Fixed

- fix pypi url

## [0.4.3] - 2025-06-17

### Added

- running github release action publishes to pypi

## [0.4.2] - 2025-05-19

### Changes

- bump cookiecutter template to ed5deb

## [0.4.1] - 2025-05-12

### Changes

- update cookiecutter template to 08b84c

## [0.4.0] - 2025-04-14

### Added

- added `--seed`, `--locale` and `--models` command line arguments

### Changes

- use merging logic from mex-common, instead of mex-backend
- implement artificial data generation without mex-extractors dependency

### Removed

- meshIds are not derived from asciimesh file anymore

## [0.3.0] - 2024-12-18

### Changes

- updated to the latest mex library versions

## [0.2.0] - 2024-11-22

### Added

- setup artificial data generation

## [0.1.0] - 2024-11-21

### Added

- initial project setup
