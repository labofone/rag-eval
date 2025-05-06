# Description

buildDataset feature defines data collection logic and pipeline to create a dataset that will be used to help the agent recommend RAG evaluation metrics and frameworks based on usecase, domain, resources, etc.

1. **why not just prompting?** the need for grounding the LLM recommendations and reasoning.
2. **why randomly collected data with no ground truth?** there's no ground truth in RAG evaluation. It's a matter of choice, a trade-off between conflicting priorities.

## Data collection logic

- **research-oriented data** for overview and comparison of evaluation frameworks (reference-based, reference-free, Ragas, etc), metrics definitions, and their applicability to different domains. (phase 1)
- **practical data**: to enhance metrics recommendations with real-world considerations and warnings. (phase 2)
- **domain-specific data**: to enhance metrics recommendations based on domain needs. (phase 3)

### Criteria

- **recency**
- **source authority/paper quality**
- **reviews/citations**
