"""
Concurrent Backend Load Testing Script & Test Suite.

Simulates 10 and 50 concurrent risk assessment requests against the backend.
Measures latency (mean, p50, p95, p99), throughput (req/s), success rate, and error breakdown.
Supports both short verification runs and configurable sustained load runs (e.g. 30-min).
"""

import os
import sys
import asyncio
import time
import argparse
from pathlib import Path
from typing import Dict, Any, List
import numpy as np
import httpx

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set test environment
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("MOCK_ML_MODE", "true")
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("MODEL_DIR", "./models")
os.environ.setdefault("FRONTEND_URL", "http://localhost:8501")

from app.main import create_app
from app.ml.model_manager import model_manager

# Sample satellite TLE payload for load testing
SAMPLE_PAYLOAD = {
    "satellite_1": {
        "line1": "1 25544U 98067A   24001.50000000  .00016717  00000-0  10270-3 0  9021",
        "line2": "2 25544  51.6400 208.9163 0006703 358.1484  30.8603 15.50216498484890",
        "name": "ISS (ZARYA)",
    },
    "satellite_2": {
        "line1": "1 48274U 21035A   24001.50000000  .00002000  00000-0  15000-3 0  9999",
        "line2": "2 48274  53.0500 120.0000 0001000  90.0000 270.0000 15.06400000100009",
        "name": "STARLINK-TEST",
    },
}


async def send_single_request(client: httpx.AsyncClient) -> Tuple_Result:
    """Send a single /risk/assess request and measure response time."""
    start = time.perf_counter()
    try:
        resp = await client.post("/risk/assess", json=SAMPLE_PAYLOAD)
        elapsed = (time.perf_counter() - start) * 1000.0  # ms
        return resp.status_code, elapsed
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000.0
        return 0, elapsed


Tuple_Result = Any


async def run_concurrent_batch(concurrency: int, total_requests: int) -> Dict[str, Any]:
    """
    Run a batch of concurrent requests with bounded concurrency.

    Args:
        concurrency: Number of parallel concurrent workers (e.g. 10, 50).
        total_requests: Total number of requests to dispatch.

    Returns:
        Dictionary containing benchmark metrics.
    """
    # Ensure app models are loaded in mock mode for load testing
    model_manager.load_models("./models", mock_mode=True)
    app = create_app()

    transport = httpx.ASGITransport(app=app)
    latencies: List[float] = []
    status_codes: Dict[int, int] = {}

    semaphore = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        async def worker():
            async with semaphore:
                status, lat = await send_single_request(client)
                latencies.append(lat)
                status_codes[status] = status_codes.get(status, 0) + 1

        overall_start = time.perf_counter()
        tasks = [asyncio.create_task(worker()) for _ in range(total_requests)]
        await asyncio.gather(*tasks)
        total_time = time.perf_counter() - overall_start

    lat_arr = np.array(latencies) if latencies else np.array([0.0])
    success_count = status_codes.get(200, 0)
    failure_count = sum(count for code, count in status_codes.items() if code != 200)

    return {
        "concurrency": concurrency,
        "total_requests": total_requests,
        "success_count": success_count,
        "failure_count": failure_count,
        "total_time_seconds": round(total_time, 3),
        "throughput_rps": round(total_requests / total_time, 2) if total_time > 0 else 0,
        "mean_latency_ms": round(float(np.mean(lat_arr)), 2),
        "p50_latency_ms": round(float(np.percentile(lat_arr, 50)), 2),
        "p95_latency_ms": round(float(np.percentile(lat_arr, 95)), 2),
        "p99_latency_ms": round(float(np.percentile(lat_arr, 99)), 2),
        "status_codes": status_codes,
    }


async def run_sustained_load(concurrency: int = 20, duration_seconds: int = 60) -> Dict[str, Any]:
    """
    Run sustained load for a configurable time duration (e.g. 60s default, or 1800s for 30-min).
    """
    model_manager.load_models("./models", mock_mode=True)
    app = create_app()

    transport = httpx.ASGITransport(app=app)
    latencies: List[float] = []
    status_codes: Dict[int, int] = {}

    end_time = time.time() + duration_seconds
    total_dispatched = 0
    semaphore = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        async def worker():
            nonlocal total_dispatched
            while time.time() < end_time:
                async with semaphore:
                    status, lat = await send_single_request(client)
                    latencies.append(lat)
                    status_codes[status] = status_codes.get(status, 0) + 1
                    total_dispatched += 1
                await asyncio.sleep(0.01)

        overall_start = time.perf_counter()
        workers = [asyncio.create_task(worker()) for _ in range(concurrency)]
        await asyncio.gather(*workers)
        actual_time = time.perf_counter() - overall_start

    lat_arr = np.array(latencies) if latencies else np.array([0.0])
    success_count = status_codes.get(200, 0)
    failure_count = sum(count for code, count in status_codes.items() if code != 200)

    return {
        "concurrency": concurrency,
        "target_duration_seconds": duration_seconds,
        "actual_duration_seconds": round(actual_time, 2),
        "total_requests": len(latencies),
        "success_count": success_count,
        "failure_count": failure_count,
        "throughput_rps": round(len(latencies) / actual_time, 2) if actual_time > 0 else 0,
        "mean_latency_ms": round(float(np.mean(lat_arr)), 2),
        "p50_latency_ms": round(float(np.percentile(lat_arr, 50)), 2),
        "p95_latency_ms": round(float(np.percentile(lat_arr, 95)), 2),
        "p99_latency_ms": round(float(np.percentile(lat_arr, 99)), 2),
        "status_codes": status_codes,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Backend Concurrent Load Test")
    parser.add_argument("--concurrency", type=int, default=10, help="Concurrency level (e.g. 10, 50)")
    parser.add_argument("--requests", type=int, default=100, help="Total requests to send")
    parser.add_argument("--sustained-seconds", type=int, default=0, help="Run sustained test for N seconds")

    args = parser.parse_args()

    if args.sustained_seconds > 0:
        print(f"--- Running Sustained Load Test ({args.sustained_seconds}s, concurrency: {args.concurrency}) ---")
        result = asyncio.run(run_sustained_load(concurrency=args.concurrency, duration_seconds=args.sustained_seconds))
    else:
        print(f"--- Running Batch Load Test ({args.requests} reqs, concurrency: {args.concurrency}) ---")
        result = asyncio.run(run_concurrent_batch(concurrency=args.concurrency, total_requests=args.requests))

    print("Load Test Results:")
    for k, v in result.items():
        print(f"  {k}: {v}")
