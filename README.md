# Policy Explainer

This is the standalone **Policy Explainer** application.

## Architecture Overview
1. **backend**: Application and API layer.
2. **frontend**: Employee UI.
3. **data_seed**: One-time synthetic data import layer.
4. **PostgreSQL**: Application's database storing policies, forms, and households.

## Relationship with Manager Repository
The manager repository (`coverant-ai-marketing`) is solely the source of synthetic seed logic/data and is **NOT** a runtime dependency.
