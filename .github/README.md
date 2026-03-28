# .github Workflows and CI/CD

This directory contains GitHub Actions workflows and issue templates.

## Structure

```
.github/
├── workflows/        # GitHub Actions CI/CD pipelines
└── ISSUE_TEMPLATE/  # Issue templates for bug reports and features
```

## Workflows

Current workflows:

- `publish-production-images.yml`: runs frontend/backend validation, builds the production Docker images, checks size thresholds, and publishes registry tags to GHCR
