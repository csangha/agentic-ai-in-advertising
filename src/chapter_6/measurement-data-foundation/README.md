# Measurement Data Foundation

## What This Is

The data infrastructure that underpins all agentic advertising. Ingests raw platform data, normalizes it into canonical schemas, integrates commerce outcomes, monitors quality, and exposes agent-queryable interfaces.

## Architecture

```
┌──────────────────────────────────────────────────────┐
│  Agent Query Interface (FastAPI + MCP Tools)          │
│  "campaigns_over_target_cpa()", "pacing_status()"    │
└────────────────────────┬─────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────┐
│  Canonical Tables (TimescaleDB Hypertables)           │
│  fact_ad_performance_hourly, dim_creative, fact_orders│
└────────────────────────┬─────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────┐
│  Normalization Layer (field mapping, currency, TZ)    │
└────────────────────────┬─────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────┐
│  Raw Storage (S3: source/entity/date/part.json)       │
└────────────────────────┬─────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────┐
│  Ingestion Connectors (Meta, Google, Amazon, TikTok)  │
└────────────────────────┬─────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────┐
│  Data Quality Monitor (freshness, completeness, gate) │
└──────────────────────────────────────────────────────┘
```

## Key Components

| Component | File | Purpose |
|-----------|------|---------|
| Data Ingestion | `services/data_ingestion.py` | Pulls data from all platforms with retry, pagination, rate limiting |
| Metric Normalizer | `services/metric_normalizer.py` | Maps platform-specific fields to canonical schema |
| Quality Monitor | `services/data_quality_monitor.py` | Freshness alerts, completeness checks, agent gate |
| Measurement MCP | `mcp_servers/measurement_server/` | MCP tools for agents to query performance data |

## Canonical Schema

```sql
fact_ad_performance_hourly:
  event_hour, platform, campaign_id, ad_id,
  impressions, clicks, spend, conversions, conversion_value,
  ctr, cpc, cpm, cpa, roas,
  ingestion_ts, source_file
```

## Data Quality Rules

- **Freshness**: Alert if platform data >30 minutes stale
- **Completeness**: Alert if record count drops >50% vs expected
- **Agent Gate**: Block optimization actions when quality fails
- **Lineage**: Every canonical record traceable to raw S3 source file

## Sample Data

- `sample_data/sample_raw_meta_response.json` — Raw Meta Ads API response (what ingestion receives)
