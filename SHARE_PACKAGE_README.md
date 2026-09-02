# Share Package README

This file explains how the Innoflame prospecting project has been prepared for sharing with another contributor.

## What is included in the share package

- Python pipeline code
- configuration example
- data requirement documentation
- CSV input descriptions
- template CSV files
- project overview presentation

## What is intentionally excluded

- local Git metadata
- temporary build artifacts
- Python cache directories
- large raw source exports
- local working material that is not needed for code or design review

## Recommended review focus

Ask the reviewer to comment on:

1. pipeline structure and maintainability
2. training assumptions and business rules
3. feature engineering and target creation
4. recommendation logic
5. output design for business users
6. missing risks, data dependencies, or production concerns

## Suggested review questions

Use these questions when sharing:

1. Is the current training logic aligned with the business rules?
2. Are there obvious risks in the feature or label design?
3. Is the recommendation logic credible enough for MVP use?
4. What would you change before productionizing this in Google Cloud?
5. Is any important data dependency or governance concern missing?

## How to share

Recommended practical flow:

1. Share the `share_package` folder or the generated ZIP file.
2. Ask the reviewer to add comments directly into the code or docs.
3. Collect feedback in one place before making the next implementation round.
