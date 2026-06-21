# Deployment Guide: Measurement Data Foundation

## Prerequisites

- Chapter 1 infrastructure deployed (Aurora + TimescaleDB, S3)
- Python 3.13+, Bedrock model access
- Platform API credentials for data ingestion

## Step 1: Verify Database Schema

The measurement tables are created by Chapter 1's migration script. Verify:
```bash
psql -h <aurora-endpoint> -U campaign_admin -d campaign_mgmt -c "\dt"
# Should show: fact_ad_performance_hourly, dim_creative, fact_orders, pacing_snapshots
```

## Step 2: Deploy Measurement MCP Server

```bash
cd mcp_servers/measurement_server
pip install -r requirements.txt
agentcore configure -e measurement_mcp_server.py --protocol MCP --runtime PYTHON_3_13 -rf requirements.txt
agentcore deploy
# Note the Runtime ARN
```

## Step 3: Configure Ingestion

Set up scheduled ingestion (every 15 minutes for active campaigns):
```bash
# Using EventBridge (production)
aws events put-rule --name "metrics-ingestion" --schedule-expression "rate(15 minutes)"

# Or run manually for testing
python -c "
import asyncio
from services.data_ingestion import DataIngestionService
svc = DataIngestionService(raw_bucket='your-raw-bucket')
job = asyncio.run(svc.ingest_platform('meta', 'act_123', '2026-01-20', '2026-01-20'))
print(f'Job: {job.job_id}, Status: {job.status}, Records: {job.records_fetched}')
"
```

## Step 4: Test Data Quality Monitor

```bash
python -c "
from services.data_quality_monitor import DataQualityMonitor
monitor = DataQualityMonitor()
# Check freshness
status = monitor.check_freshness('meta', max_stale_minutes=30)
print(f'Meta freshness: {status}')
"
```

## Step 5: Test Agent Query Interface

```bash
# Query via MCP server
curl -X POST https://<measurement-mcp-endpoint> \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "query_performance", "arguments": {"campaign_id": "camp-fitpulse-001", "time_range_hours": 24}}}'
```

## Step 6: Load Sample Data

```bash
# Insert sample performance metrics for testing
psql -h <endpoint> -U campaign_admin -d campaign_mgmt -c "
INSERT INTO fact_ad_performance_hourly (event_hour, platform, account_id, campaign_id, ad_id, impressions, clicks, spend, conversions, ctr, cpc, cpm, cpa)
VALUES
  (NOW() - INTERVAL '1 hour', 'meta', 'act_001', 'camp-fitpulse-001', 'ad_001', 12500, 375, 300.00, 9, 0.03, 0.80, 24.00, 33.33),
  (NOW() - INTERVAL '1 hour', 'google', 'act_002', 'camp-fitpulse-001', 'ad_002', 10000, 450, 222.50, 6, 0.045, 0.49, 22.25, 37.08),
  (NOW() - INTERVAL '1 hour', 'amazon', 'act_003', 'camp-fitpulse-001', 'ad_003', 6250, 225, 112.50, 3, 0.036, 0.50, 18.00, 37.50),
  (NOW() - INTERVAL '1 hour', 'tiktok', 'act_004', 'camp-fitpulse-001', 'ad_004', 7500, 300, 75.12, 1, 0.04, 0.25, 10.02, 75.12);
"
```

## Running Locally

```bash
# Run the measurement MCP server locally
cd mcp_servers/measurement_server
python measurement_mcp_server.py  # stdio mode (for testing with MCP client)
```
