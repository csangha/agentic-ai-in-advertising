# Chapter 6: Measurement Systems — The Data Foundation

## Purpose

In an agentic system, measurement is not the end of the workflow — it's the foundation that makes everything else possible. An optimization agent can only act intelligently if it's observing the right signals. This chapter builds the measurement infrastructure that all agents depend on.

## Use Cases

| Use Case | Description |
|----------|-------------|
| [Measurement Data Foundation](./measurement-data-foundation/) | Multi-platform ingestion, normalization, canonical schemas, quality monitoring, agent-queryable serving |

## Key Concepts

- **Measurement ≠ Reporting**: Reporting summarizes for humans; measurement creates operationally trustworthy data for agents
- **Canonical Schema**: Platform-specific metrics normalized into one comparable structure
- **Data Lineage**: Every derived metric traceable back to its raw source
- **Agent Gate**: Agents CANNOT act when data quality fails (freshness, completeness)
- **Three Time Horizons**: Real-time (minutes), intra-day (hours), historical (days+)
