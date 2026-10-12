#!/usr/bin/env bash
# Real-time log watcher for Azure Function App via Application Insights

APP_INSIGHTS="cadefigurinha-appinsights"
RG="cadefigurinha-rg"

echo "Watching logs for $APP_INSIGHTS (Ctrl+C to stop)..."

watch -n 3 "az monitor app-insights query \
  --app '$APP_INSIGHTS' \
  --resource-group '$RG' \
  --analytics-query 'traces | where message !has \"Transmission succeeded\" and message !has \"Response status\" and message !has \"Request URL\" | order by timestamp desc | take 15 | project timestamp, message' \
  --query 'tables[0].rows' \
  --output table"
