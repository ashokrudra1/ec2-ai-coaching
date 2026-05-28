# backend/config/cloudwatch_config.py
"""
AWS CloudWatch logging configuration for production monitoring.
Enables centralized log aggregation and metrics publishing.
"""
import logging
import json
import os
from datetime import datetime, timezone
from aws_lambda_powertools.utilities.typing import LambdaContext
import boto3

class CloudWatchHandler(logging.Handler):
    """Custom logging handler that publishes logs to AWS CloudWatch"""
    
    def __init__(self, log_group: str, log_stream: str, region: str = "ap-south-1"):
        super().__init__()
        self.log_group = log_group
        self.log_stream = log_stream
        self.region = region
        self.client = boto3.client("logs", region_name=region)
        self.sequence_token = None
        self._initialize_stream()
    
    def _initialize_stream(self):
        """Create CloudWatch log group and stream if they don't exist"""
        try:
            # Create log group if it doesn't exist
            try:
                self.client.create_log_group(logGroupName=self.log_group)
            except self.client.exceptions.ResourceAlreadyExistsException:
                pass
            
            # Create log stream if it doesn't exist
            try:
                self.client.create_log_stream(
                    logGroupName=self.log_group,
                    logStreamName=self.log_stream
                )
            except self.client.exceptions.ResourceAlreadyExistsException:
                # Get existing sequence token
                response = self.client.describe_log_streams(
                    logGroupName=self.log_group,
                    logStreamNamePrefix=self.log_stream
                )
                if response["logStreams"]:
                    self.sequence_token = response["logStreams"][0].get("uploadSequenceToken")
        except Exception as e:
            print(f"Failed to initialize CloudWatch stream: {e}")
    
    def emit(self, record):
        """Send log record to CloudWatch"""
        try:
            log_entry = self.format(record)
            
            put_log_events_kwargs = {
                "logGroupName": self.log_group,
                "logStreamName": self.log_stream,
                "logEvents": [
                    {
                        "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                        "message": log_entry
                    }
                ]
            }
            
            if self.sequence_token:
                put_log_events_kwargs["sequenceToken"] = self.sequence_token
            
            response = self.client.put_log_events(**put_log_events_kwargs)
            self.sequence_token = response.get("nextSequenceToken")
        except Exception:
            self.handleError(record)


def setup_cloudwatch_logging(
    app_name: str = "veda-ai-coaching",
    environment: str = "production",
    region: str = "ap-south-1"
):
    """
    Setup AWS CloudWatch logging for the application.
    
    Args:
        app_name: Application name (used in log group name)
        environment: Environment (development, staging, production)
        region: AWS region
    """
    if not os.getenv("AWS_ACCESS_KEY_ID"):
        return  # CloudWatch not configured, skip
    
    log_group = f"/veda-ai-coaching/{environment}"
    log_stream = f"{app_name}-{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    
    handler = CloudWatchHandler(log_group, log_stream, region)
    handler.setFormatter(logging.Formatter(
        '{"timestamp":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}'
    ))
    
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)


class CloudWatchMetrics:
    """Publish custom metrics to CloudWatch"""
    
    def __init__(self, namespace: str = "VedaAICoaching", region: str = "ap-south-1"):
        self.namespace = namespace
        self.region = region
        self.client = boto3.client("cloudwatch", region_name=region)
    
    def put_metric(
        self,
        metric_name: str,
        value: float,
        unit: str = "Count",
        dimensions: dict = None
    ):
        """Publish a custom metric to CloudWatch"""
        try:
            metric_data = {
                "MetricName": metric_name,
                "Value": value,
                "Unit": unit,
                "Timestamp": datetime.now(timezone.utc)
            }
            
            if dimensions:
                metric_data["Dimensions"] = [
                    {"Name": k, "Value": str(v)} for k, v in dimensions.items()
                ]
            
            self.client.put_metric_data(
                Namespace=self.namespace,
                MetricData=[metric_data]
            )
        except Exception as e:
            logging.error(f"Failed to publish metric {metric_name}: {e}")
    
    def put_api_latency(self, endpoint: str, latency_ms: float, status_code: int):
        """Publish API latency metric"""
        self.put_metric(
            metric_name="APILatency",
            value=latency_ms,
            unit="Milliseconds",
            dimensions={"Endpoint": endpoint, "StatusCode": status_code}
        )
    
    def put_database_query_time(self, query_type: str, duration_ms: float):
        """Publish database query time metric"""
        self.put_metric(
            metric_name="DatabaseQueryTime",
            value=duration_ms,
            unit="Milliseconds",
            dimensions={"QueryType": query_type}
        )
    
    def put_celery_task_duration(self, task_name: str, duration_ms: float):
        """Publish Celery task duration metric"""
        self.put_metric(
            metric_name="CeleryTaskDuration",
            value=duration_ms,
            unit="Milliseconds",
            dimensions={"TaskName": task_name}
        )
