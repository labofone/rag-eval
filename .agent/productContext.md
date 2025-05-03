# Product Context

This document explains the purpose of the project from a product perspective, including the problems it solves, how it should work, and the user experience goals.

## Problem Solved

This API addresses the need for automated and efficient evaluation of RAG pipelines. It solves the problem of manually assessing the quality of generated responses, which is time-consuming and subjective.

## How it Works

The API receives a query, context, and generated response. It then uses reference-free metrics (Correctness, Faithfulness, Relevancy) to evaluate the response's quality. The evaluation is performed asynchronously, and the results are stored and can be retrieved later.

## User Experience Goals

- Simple API for easy integration with existing RAG pipelines.
- Fast evaluation times to enable rapid iteration and experimentation.
- Clear and interpretable evaluation metrics to facilitate performance analysis.
- Agentic selection of evaluation metrics based on natural language queries.
