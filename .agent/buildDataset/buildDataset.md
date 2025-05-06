## Description

buildDataset feature defines data collection logic and pipeline to create a dataset that will be used to help the agent recommend RAG evaluation metrics and frameworks based on usecase, domain, resources, etc.

1. **why not just prompting?** the need for grounding the LLM recommendations and reasoning.
2. **why randomly collected data with no ground truth?** there's no ground truth in RAG evaluation. It's a matter of choice, a trade-off between conflicting priorities.
