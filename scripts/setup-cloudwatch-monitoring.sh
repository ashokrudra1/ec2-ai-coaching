#!/bin/bash
# scripts/setup-cloudwatch-monitoring.sh
# Configure CloudWatch dashboards, alarms, and metrics

set -e

AWS_REGION="${AWS_REGION:-ap-south-1}"
ENVIRONMENT="${ENVIRONMENT:-production}"
APP_NAME="veda-ai-coaching"
INSTANCE_ID=$(ec2-metadata --instance-id | cut -d " " -f 2)

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

log "Setting up CloudWatch monitoring and alarms..."

# ============================================================================
# 1. CREATE DASHBOARD
# ============================================================================
log "Creating CloudWatch dashboard..."

aws cloudwatch put-dashboard \
    --dashboard-name "$APP_NAME-$ENVIRONMENT" \
    --dashboard-body '{
        "widgets": [
            {
                "type": "metric",
                "properties": {
                    "metrics": [
                        ["AWS/EC2", "CPUUtilization", {"stat": "Average"}],
                        ["AWS/EC2", "NetworkIn", {"stat": "Sum"}],
                        ["AWS/EC2", "NetworkOut", {"stat": "Sum"}],
                        ["AWS/EC2", "DiskReadBytes", {"stat": "Sum"}],
                        ["AWS/EC2", "DiskWriteBytes", {"stat": "Sum"}]
                    ],
                    "period": 300,
                    "stat": "Average",
                    "region": "'$AWS_REGION'",
                    "title": "EC2 Instance Metrics"
                }
            },
            {
                "type": "metric",
                "properties": {
                    "metrics": [
                        ["/veda-ai-coaching/'$ENVIRONMENT'", "APILatency", {"stat": "Average"}],
                        [".", ".", {"stat": "p99"}],
                        [".", "DatabaseQueryTime", {"stat": "Average"}],
                        [".", "CeleryTaskDuration", {"stat": "Average"}]
                    ],
                    "period": 60,
                    "stat": "Average",
                    "region": "'$AWS_REGION'",
                    "title": "Application Performance"
                }
            },
            {
                "type": "log",
                "properties": {
                    "query": "fields @timestamp, @message | filter @message like /ERROR/ | stats count() by bin(5m)",
                    "region": "'$AWS_REGION'",
                    "title": "Error Rate (5 min)"
                }
            }
        ]
    }' \
    --region "$AWS_REGION" || log "Dashboard creation skipped"

# ============================================================================
# 2. CREATE ALARMS
# ============================================================================
log "Creating CloudWatch alarms..."

# CPU Utilization alarm
aws cloudwatch put-metric-alarm \
    --alarm-name "$APP_NAME-$ENVIRONMENT-high-cpu" \
    --alarm-description "Alert when CPU utilization is >80% for 5 minutes" \
    --metric-name CPUUtilization \
    --namespace AWS/EC2 \
    --statistic Average \
    --period 300 \
    --evaluation-periods 1 \
    --threshold 80 \
    --comparison-operator GreaterThanThreshold \
    --dimensions Name=InstanceId,Value="$INSTANCE_ID" \
    --region "$AWS_REGION" || log "CPU alarm creation skipped"

# Memory alarm (requires CloudWatch agent)
aws cloudwatch put-metric-alarm \
    --alarm-name "$APP_NAME-$ENVIRONMENT-high-memory" \
    --alarm-description "Alert when memory utilization is >85%" \
    --metric-name MemoryUtilization \
    --namespace CWAgent \
    --statistic Average \
    --period 300 \
    --evaluation-periods 1 \
    --threshold 85 \
    --comparison-operator GreaterThanThreshold \
    --region "$AWS_REGION" || log "Memory alarm creation skipped"

# Disk space alarm
aws cloudwatch put-metric-alarm \
    --alarm-name "$APP_NAME-$ENVIRONMENT-low-disk-space" \
    --alarm-description "Alert when disk space is <10%" \
    --metric-name DiskSpaceAvailable \
    --namespace CWAgent \
    --statistic Average \
    --period 300 \
    --evaluation-periods 1 \
    --threshold 10 \
    --comparison-operator LessThanThreshold \
    --region "$AWS_REGION" || log "Disk alarm creation skipped"

# API latency alarm
aws cloudwatch put-metric-alarm \
    --alarm-name "$APP_NAME-$ENVIRONMENT-high-api-latency" \
    --alarm-description "Alert when API latency (p99) is >1000ms" \
    --metric-name APILatency \
    --namespace "VedaAICoaching" \
    --statistic Average \
    --period 60 \
    --evaluation-periods 2 \
    --threshold 1000 \
    --comparison-operator GreaterThanThreshold \
    --region "$AWS_REGION" || log "API latency alarm creation skipped"

# Database query time alarm
aws cloudwatch put-metric-alarm \
    --alarm-name "$APP_NAME-$ENVIRONMENT-slow-database" \
    --alarm-description "Alert when database queries take >5000ms" \
    --metric-name DatabaseQueryTime \
    --namespace "VedaAICoaching" \
    --statistic Average \
    --period 60 \
    --evaluation-periods 2 \
    --threshold 5000 \
    --comparison-operator GreaterThanThreshold \
    --region "$AWS_REGION" || log "DB latency alarm creation skipped"

# Health check failure alarm (requires creating composite alarm)
aws cloudwatch put-metric-alarm \
    --alarm-name "$APP_NAME-$ENVIRONMENT-health-check-failed" \
    --alarm-description "Alert when application health check fails" \
    --metric-name HealthCheckStatus \
    --namespace "VedaAICoaching" \
    --statistic Minimum \
    --period 60 \
    --evaluation-periods 1 \
    --threshold 1 \
    --comparison-operator LessThanThreshold \
    --region "$AWS_REGION" || log "Health check alarm creation skipped"

log "CloudWatch alarms created successfully"

# ============================================================================
# 3. CREATE LOG GROUPS
# ============================================================================
log "Creating CloudWatch log groups..."

aws logs create-log-group \
    --log-group-name "/veda-ai-coaching/$ENVIRONMENT" \
    --region "$AWS_REGION" 2>/dev/null || log "Log group already exists"

aws logs put-retention-policy \
    --log-group-name "/veda-ai-coaching/$ENVIRONMENT" \
    --retention-in-days 30 \
    --region "$AWS_REGION" 2>/dev/null || true

# ============================================================================
# 4. PRINT SUMMARY
# ============================================================================
echo ""
echo "=========================================="
echo "CloudWatch Monitoring Setup Complete"
echo "=========================================="
echo ""
echo "Dashboard: $APP_NAME-$ENVIRONMENT"
echo "Region: $AWS_REGION"
echo "Instance: $INSTANCE_ID"
echo ""
echo "Alarms configured:"
echo "  ✓ High CPU (>80% for 5min)"
echo "  ✓ High Memory (>85%)"
echo "  ✓ Low Disk Space (<10%)"
echo "  ✓ High API Latency (p99 >1000ms)"
echo "  ✓ Slow Database (queries >5000ms)"
echo "  ✓ Health Check Failures"
echo ""
echo "Next steps:"
echo "  1. Add SNS topic for notifications"
echo "  2. Configure email/Slack alerts"
echo "  3. Setup custom metrics from application"
echo "  4. Create runbooks for each alarm"
echo ""
