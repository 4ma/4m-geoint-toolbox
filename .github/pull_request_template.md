### Description

Provide a brief description of the PR's purpose and a bulleted list of changes.

### Readability & Best Practices
- [ ] Self-review completed (manually or via AI tool).
- [ ] Execution instructions for all environments (Dev/Prod) are clear in README.md.
- [ ] All code is type-hinted (Python).
- [ ] Common functionality utilizes external/shared libraries where possible.
- [ ] Directory structure is logical and easy to navigate.
- [ ] Functions and files are kept to a reasonable size.

### Testing
- [ ] CI pipeline passed.
- [ ] Local testing instructions are documented in README.md.
- [ ] Codecov reports at least 80% test coverage.
- [ ] Large test assets are stored in S3 (`s3://4m-test-assets-dev`) rather than the repo.

### Monitoring
- [ ] Errors are logged clearly and are easily accessible.
- [ ] Error monitoring and alerting are configured appropriately.

### Security
- [ ] No sensitive data is exposed to AI tools (as defined in `ai-gate-keeper.yaml`).
- [ ] SQL inputs are parameterized and protected against injection.
- [ ] New secrets are stored in the Vault (not in code or README).
- [ ] Snyk security checks passed.

### I/O & Data
- [ ] S3 output files are stored in a path structure that is programmatically accessible.
- [ ] Required DB schema/data changes are applied or included in this commit.
- [ ] All required cloud resources are accessible across all environments.
