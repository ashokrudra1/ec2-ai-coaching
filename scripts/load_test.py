#!/usr/bin/env python3
# scripts/load_test.py
# Load testing with Locust - baseline capacity planning

import os
from locust import HttpUser, task, between, events, TaskSet
from datetime import datetime

BASE_URL = os.getenv("BASE_URL", "https://vedaactivewellness.xyz")
NUM_USERS = int(os.getenv("NUM_USERS", "50"))
SPAWN_RATE = int(os.getenv("SPAWN_RATE", "5"))
DURATION_SECONDS = int(os.getenv("DURATION_SECONDS", "300"))


class APITasks(TaskSet):
    """Define API test scenarios"""
    
    @task(10)
    def health_check(self):
        """Health check endpoint - high frequency"""
        self.client.get("/health", name="/health")
    
    @task(5)
    def ping(self):
        """Ping endpoint"""
        self.client.get("/ping", name="/ping")
    
    @task(3)
    def dashboard_stats(self):
        """Dashboard statistics"""
        self.client.get("/api/stats", name="/api/stats")
    
    @task(2)
    def activities(self):
        """Get recent activities"""
        self.client.get("/api/activities", name="/api/activities")
    
    @task(1)
    def health_metrics(self):
        """Health metrics"""
        self.client.get("/health/metrics", name="/health/metrics")


class VedaUser(HttpUser):
    """User behavior"""
    tasks = [APITasks]
    wait_time = between(1, 3)  # Wait 1-3 seconds between requests


# ============================================================================
# EVENT HANDLERS FOR DETAILED REPORTING
# ============================================================================

stats_data = {
    "total_requests": 0,
    "total_failures": 0,
    "total_success": 0,
    "response_times": [],
    "error_types": {}
}


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, response, context, exception, **kwargs):
    """Track request statistics"""
    stats_data["total_requests"] += 1
    stats_data["response_times"].append(response_time)
    
    if exception:
        stats_data["total_failures"] += 1
        error_type = type(exception).__name__
        stats_data["error_types"][error_type] = stats_data["error_types"].get(error_type, 0) + 1
    else:
        stats_data["total_success"] += 1


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Print final report"""
    print("\n" + "=" * 80)
    print("LOAD TEST REPORT")
    print("=" * 80)
    print(f"Test Duration: {DURATION_SECONDS} seconds")
    print(f"Peak Concurrent Users: {NUM_USERS}")
    print(f"Spawn Rate: {SPAWN_RATE} users/second")
    print("")
    
    print("RESULTS SUMMARY:")
    print(f"  Total Requests: {stats_data['total_requests']}")
    print(f"  Successful: {stats_data['total_success']}")
    print(f"  Failed: {stats_data['total_failures']}")
    print(f"  Success Rate: {(stats_data['total_success'] / max(stats_data['total_requests'], 1) * 100):.2f}%")
    print("")
    
    if stats_data['response_times']:
        response_times_sorted = sorted(stats_data['response_times'])
        print("RESPONSE TIME STATISTICS (ms):")
        print(f"  Min: {min(response_times_sorted):.2f}ms")
        print(f"  Max: {max(response_times_sorted):.2f}ms")
        print(f"  Mean: {sum(response_times_sorted) / len(response_times_sorted):.2f}ms")
        print(f"  Median (p50): {response_times_sorted[int(len(response_times_sorted) * 0.50)]:.2f}ms")
        print(f"  p95: {response_times_sorted[int(len(response_times_sorted) * 0.95)]:.2f}ms")
        print(f"  p99: {response_times_sorted[int(len(response_times_sorted) * 0.99)]:.2f}ms")
    print("")
    
    if stats_data['error_types']:
        print("ERROR BREAKDOWN:")
        for error_type, count in sorted(stats_data['error_types'].items(), key=lambda x: x[1], reverse=True):
            print(f"  {error_type}: {count}")
    print("")
    
    print("=" * 80)
    print("CAPACITY PLANNING RECOMMENDATIONS:")
    if stats_data['total_failures'] == 0:
        print("  ✓ System handled load without errors")
        if stats_data['response_times']:
            p99 = sorted(stats_data['response_times'])[int(len(stats_data['response_times']) * 0.99)]
            if p99 < 500:
                print("  ✓ Response times excellent (p99 < 500ms)")
                print(f"  ✓ Can handle at least {NUM_USERS * 2} concurrent users")
            elif p99 < 1000:
                print("  ✓ Response times good (p99 < 1s)")
                print(f"  ✓ Current capacity: {NUM_USERS} users")
    else:
        failure_rate = stats_data['total_failures'] / stats_data['total_requests']
        print(f"  ⚠ {failure_rate * 100:.1f}% failure rate detected")
        print(f"  Reduce users to {max(10, int(NUM_USERS * 0.7))}")
    print("")
    print("=" * 80)


if __name__ == "__main__":
    print(f"Load Test Configuration:")
    print(f"  Base URL: {BASE_URL}")
    print(f"  Peak Users: {NUM_USERS}")
    print(f"  Spawn Rate: {SPAWN_RATE} users/second")
    print(f"  Duration: {DURATION_SECONDS} seconds")
    print(f"  Start Time: {datetime.now()}")
    print("")
