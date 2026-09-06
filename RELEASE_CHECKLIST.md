# Release Checklist

## Automated verification

- [ ] Full pytest suite passes
- [ ] Python compilation succeeds
- [ ] `pip check` reports no broken requirements
- [ ] Bandit reports no unresolved security findings
- [ ] Dependency audit passes with documented ChromaDB exceptions
- [ ] GitHub Actions workflow is green
- [ ] Working tree is clean

## Runtime verification

- [ ] Docker image builds successfully
- [ ] Compose configuration validates
- [ ] API container becomes healthy
- [ ] `/health/live` returns `alive`
- [ ] `/health/ready` returns `ready`
- [ ] Ollama is reachable from the container
- [ ] Pipeline smoke test succeeds

## Evaluation evidence

- [ ] Retrieval development benchmark recorded
- [ ] Retrieval held-out benchmark recorded
- [ ] Generation development benchmark recorded
- [ ] Generation held-out benchmark recorded
- [ ] Generation quality gates pass
- [ ] Safety benchmark passes
- [ ] Known limitations are documented

## Release

- [ ] README contains installation and operating instructions
- [ ] SECURITY.md contains the threat model and mitigations
- [ ] Evaluation reports are committed
- [ ] Release commit is pushed
- [ ] GitHub Actions passes
- [ ] Version tag is created from the reviewed commit