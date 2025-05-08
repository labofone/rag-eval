# Description

The `buildDataset` feature defines data collection logic and a pipeline to create a dataset that will be used to help the agent recommend RAG evaluation metrics and frameworks based on use case, domain, resources, etc. This dataset ensures that recommendations are grounded in research and practical considerations.

1. **Why not just prompting?** The need for grounding the LLM recommendations and reasoning.
2. **Why randomly collected data with no ground truth?** There's no ground truth in RAG evaluation. It's a matter of choice, a trade-off between conflicting priorities.

## Data Collection Logic

### Data Categories

- **Research-Oriented Data**: Provides an overview and comparison of evaluation frameworks (reference-based, reference-free, Ragas, etc.), metrics definitions, and their applicability to different domains. **(Phase 1)**
- **Practical Data**: Enhances metrics recommendations with real-world considerations and warnings. **(Phase 2)**
- **Domain-Specific Data**: Enhances metrics recommendations based on domain needs. **(Phase 3)**

### Data Evaluation Criteria

- **Relevance**: Ensures the data aligns with the intended use case.
- **Recency**: Prioritizes up-to-date information.
- **Source Authority/Paper Quality**: Evaluates the credibility and quality of the source.
- **Reviews/Citations**: Considers the impact and recognition of the source.

### Challenges and Mitigation

- **Data Quality**: Implement automated checks and manual reviews to ensure high-quality data.
- **Scalability**: Use efficient data collection and storage mechanisms to handle large datasets.
- **Bias**: Regularly review and update criteria to minimize bias.
