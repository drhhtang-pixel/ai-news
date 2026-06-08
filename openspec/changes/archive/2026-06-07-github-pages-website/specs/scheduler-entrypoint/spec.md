## MODIFIED Requirements

### Requirement: run.sh provides a cron-compatible wrapper

The `run.sh` script SHALL load environment variables from a `.env` file if present, invoke `python3 agent.py`, then invoke `python3 publish.py`, and finally push changes to the GitHub remote repository.

#### Scenario: Cron invocation with .env

- **WHEN** cron calls `run.sh` and a `.env` file exists in the same directory
- **THEN** the script SHALL source the `.env` file before running the agent

#### Scenario: run.sh includes a sample crontab comment

- **WHEN** a developer opens `run.sh`
- **THEN** they SHALL see a commented example crontab entry showing daily execution at 08:00

#### Scenario: run.sh runs publish.py after agent.py

- **WHEN** `run.sh` executes and `agent.py` exits with code 0
- **THEN** `run.sh` SHALL invoke `python3 publish.py` to regenerate the static site

#### Scenario: run.sh pushes to GitHub after publish

- **WHEN** `publish.py` completes successfully
- **THEN** `run.sh` SHALL stage `docs/` and `summaries.md`, commit with a dated message, and push to the remote

#### Scenario: git push failure does not affect agent exit code

- **WHEN** the git push fails (e.g., network error)
- **THEN** the error SHALL be printed to stderr
- **THEN** `run.sh` SHALL exit with code 0 (agent and publish both succeeded)

##### Example: run.sh execution sequence

| Step | Command | On failure |
|---|---|---|
| 1 | `python3 agent.py` | Exit immediately with agent's exit code |
| 2 | `python3 publish.py` | Print error, continue to git |
| 3 | `git add docs/ summaries.md` | Print error, skip commit |
| 4 | `git commit -m "Daily summary YYYY-MM-DD"` | Print error, skip push |
| 5 | `git push` | Print error to stderr, exit 0 |
