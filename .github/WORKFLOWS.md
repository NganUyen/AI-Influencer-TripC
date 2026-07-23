# GitHub Workflows and CI/CD

This directory contains GitHub Actions workflows and issue templates.

## Structure

```
.github/
├── workflows/        # GitHub Actions CI/CD pipelines
└── ISSUE_TEMPLATE/  # Issue templates for bug reports and features
```

## Workflows

Current workflows:

- `ci.yml`: pull-request and branch quality gates for frontend, backend, shell, and Docker Compose changes
- `publish-production-images.yml`: runs the backend publication gate, builds production Docker images, checks size thresholds, and publishes commit-SHA and `latest` tags to GHCR
