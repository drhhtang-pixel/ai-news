# scheduler-entrypoint

Cron-compatible entry point: a Python script (`agent.py`) and shell wrapper (`run.sh`) that can be invoked by system cron or any task scheduler with no interactive input required.

## Overview

- **Entry point**: `python agent.py` (or `python3 agent.py`)
- **Shell wrapper**: `run.sh` — sources `.env` if present, then delegates to `agent.py`
- **Configuration**: 100% environment-variable-driven; no config files or interactive prompts

## Requirements

### Requirement: Agent exits cleanly with a status code

The entry point SHALL exit with code `0` on success and a non-zero code on failure, making it compatible with cron error detection.

#### Scenario: Successful run

- **WHEN** the agent completes and a summary is written
- **THEN** the process SHALL exit with code `0`

#### Scenario: Missing API key

- **WHEN** `ANTHROPIC_API_KEY` or `TAVILY_API_KEY` is not set
- **THEN** the process SHALL print an error message to stderr and exit with code `1`

##### Example: missing key errors

| Missing variable | stderr message | exit code |
|---|---|---|
| ANTHROPIC_API_KEY | `Error: ANTHROPIC_API_KEY is not set` | 1 |
| TAVILY_API_KEY | `Error: TAVILY_API_KEY is not set` | 1 |

### Requirement: Configuration is read from environment variables

The agent SHALL read all configuration from environment variables, with documented defaults, so that it can be invoked by cron without modification.

#### Scenario: Default configuration

- **WHEN** only `ANTHROPIC_API_KEY` and `TAVILY_API_KEY` are set
- **THEN** the agent SHALL use `SEARCH_TOPIC="AI news today"` and `OUTPUT_FILE="summaries.md"`

#### Scenario: Custom configuration

- **WHEN** `SEARCH_TOPIC` and `OUTPUT_FILE` are set in the environment
- **THEN** the agent SHALL use those values instead of the defaults

### Requirement: run.sh provides a cron-compatible wrapper

The `run.sh` script SHALL load environment variables from a `.env` file if present, then invoke `python agent.py`.

#### Scenario: Cron invocation with .env

- **WHEN** cron calls `run.sh` and a `.env` file exists in the same directory
- **THEN** the script SHALL source the `.env` file before running the agent

#### Scenario: run.sh includes a sample crontab comment

- **WHEN** a developer opens `run.sh`
- **THEN** they SHALL see a commented example crontab entry showing daily execution at 08:00

## Implementation Notes

- `validate_env()` in `agent.py` checks keys in order: `ANTHROPIC_API_KEY` first, then `TAVILY_API_KEY`; the first missing key causes an immediate `sys.exit(1)`
- `run.sh` resolves its own directory via `SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"` to support invocation from arbitrary working directories
- `.env` is loaded with `set -a` / `source` / `set +a` so all variables are exported automatically
- The sample crontab comment in `run.sh`: `# 0 8 * * * /path/to/run.sh >> /path/to/cron.log 2>&1`
- Normal (non-error) output goes to stdout; error messages go to stderr — compatible with cron log splitting via `2>&1` or separate redirect
