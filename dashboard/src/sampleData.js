// Auto-generated from docs/sample_run_output/ — do not edit by hand.
// Re-run: python3 scripts/gen_sample_data.py
// Used by the dashboard demo mode so you can explore without Docker.

export const DEMO_MULTI_AGENT = {
  "run_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "mode": "multi_agent",
  "status": "finished",
  "termination_reason": "target_hit",
  "iterations": [
    {
      "id": "3eff58d2-2ff1-43f9-9cc3-63b9e35799ef",
      "run_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "iteration_number": 1,
      "config_applied": {
        "pool_size": 5,
        "query_timeout_ms": 5000,
        "cache_ttl_seconds": 60,
        "batch_size": 100,
        "retry_interval_ms": 100
      },
      "metrics": {
        "p95_latency_ms": 812,
        "p99_latency_ms": 1240,
        "throughput_rps": 43.2,
        "error_rate": 0.042,
        "avg_latency_ms": 527.8,
        "median_latency_ms": 446.6,
        "request_count": 2592,
        "failure_count": 109
      },
      "judge_analysis": {
        "bottleneck": "pool_exhaustion",
        "severity": "high",
        "trend": "unknown",
        "reasoning": "Pool exhausted under 100 VUs. asyncpg queue backing up — p95 climbing above 800ms with 4.2% error rate. Increasing pool_size is the highest-leverage single change.",
        "recommended_direction": {
          "pool_size": "increase",
          "query_timeout_ms": "decrease"
        }
      },
      "judge_vision_analysis": {
        "visual_insight": "Vision analysis unavailable",
        "error": "No serverless vision model available on Fireworks as of Jul 2026"
      },
      "optimizer_proposal": {
        "proposed_config": {
          "pool_size": 10,
          "query_timeout_ms": 4500,
          "cache_ttl_seconds": 60,
          "batch_size": 100,
          "retry_interval_ms": 100
        },
        "rationale": "Primary action: pool size — increase. Pool exhausted under 100 VUs. asyncpg queue backing up — p95 climbing above 800m...",
        "expected_effect": "Target p95 reduction of 10–20% based on bottleneck type and prior iteration delta.",
        "confidence": "high"
      },
      "veto_event": null,
      "final_decision": {
        "pool_size": 5,
        "query_timeout_ms": 5000,
        "cache_ttl_seconds": 60,
        "batch_size": 100,
        "retry_interval_ms": 100
      },
      "baseline_decision": null,
      "created_at": "2026-07-16T14:00:00+00:00"
    },
    {
      "id": "d8078cad-a44b-41d1-b674-b3313a993812",
      "run_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "iteration_number": 2,
      "config_applied": {
        "pool_size": 15,
        "query_timeout_ms": 5000,
        "cache_ttl_seconds": 60,
        "batch_size": 100,
        "retry_interval_ms": 100
      },
      "metrics": {
        "p95_latency_ms": 530,
        "p99_latency_ms": 780,
        "throughput_rps": 68.1,
        "error_rate": 0.011,
        "avg_latency_ms": 344.5,
        "median_latency_ms": 291.5,
        "request_count": 4086,
        "failure_count": 45
      },
      "judge_analysis": {
        "bottleneck": "pool_exhaustion",
        "severity": "medium",
        "trend": "improving",
        "reasoning": "Pool expansion cut p95 by 35%. Error rate dropped from 4.2% to 1.1%. Still some queue depth under peak load — pool still slightly undersized for 100 VUs with mixed CRUD.",
        "recommended_direction": {
          "pool_size": "increase",
          "cache_ttl_seconds": "increase"
        }
      },
      "judge_vision_analysis": {
        "visual_insight": "Vision analysis unavailable",
        "error": "No serverless vision model available on Fireworks as of Jul 2026"
      },
      "optimizer_proposal": {
        "proposed_config": {
          "pool_size": 20,
          "query_timeout_ms": 5000,
          "cache_ttl_seconds": 120,
          "batch_size": 100,
          "retry_interval_ms": 100
        },
        "rationale": "Primary action: pool size — increase. Pool expansion cut p95 by 35%. Error rate dropped from 4.2% to 1.1%. Still some ...",
        "expected_effect": "Target p95 reduction of 10–20% based on bottleneck type and prior iteration delta.",
        "confidence": "high"
      },
      "veto_event": null,
      "final_decision": {
        "pool_size": 15,
        "query_timeout_ms": 5000,
        "cache_ttl_seconds": 60,
        "batch_size": 100,
        "retry_interval_ms": 100
      },
      "baseline_decision": null,
      "created_at": "2026-07-16T14:08:00+00:00"
    },
    {
      "id": "bdf41068-f015-4d72-8ecc-11a1edf99176",
      "run_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "iteration_number": 3,
      "config_applied": {
        "pool_size": 25,
        "query_timeout_ms": 5000,
        "cache_ttl_seconds": 60,
        "batch_size": 100,
        "retry_interval_ms": 100
      },
      "metrics": {
        "p95_latency_ms": 390,
        "p99_latency_ms": 570,
        "throughput_rps": 78.4,
        "error_rate": 0.003,
        "avg_latency_ms": 253.5,
        "median_latency_ms": 214.5,
        "request_count": 4704,
        "failure_count": 14
      },
      "judge_analysis": {
        "bottleneck": "cache_miss_rate",
        "severity": "medium",
        "trend": "improving",
        "reasoning": "Pool now sufficient. Product-search queries are the remaining bottleneck — 40% of requests are /products/search hits, but cache TTL at 60s means frequent cache misses under shifting query patterns.",
        "recommended_direction": {
          "cache_ttl_seconds": "increase",
          "pool_size": "maintain"
        }
      },
      "judge_vision_analysis": {
        "visual_insight": "Vision analysis unavailable",
        "error": "No serverless vision model available on Fireworks as of Jul 2026"
      },
      "optimizer_proposal": {
        "proposed_config": {
          "pool_size": 25,
          "query_timeout_ms": 5000,
          "cache_ttl_seconds": 120,
          "batch_size": 100,
          "retry_interval_ms": 100
        },
        "rationale": "Primary action: cache ttl seconds — increase. Pool now sufficient. Product-search queries are the remaining bottleneck — 40% o...",
        "expected_effect": "Target p95 reduction of 10–20% based on bottleneck type and prior iteration delta.",
        "confidence": "high"
      },
      "veto_event": {
        "vetoed": true,
        "reason": "pool_size 4 below minimum safe value of 5",
        "revision_attempt": 1,
        "original_proposal": {
          "pool_size": 4,
          "cache_ttl_seconds": 300
        },
        "revision_proposal": {
          "pool_size": 25,
          "cache_ttl_seconds": 300
        },
        "revision_accepted": true,
        "revision_veto_reason": null
      },
      "final_decision": {
        "pool_size": 25,
        "query_timeout_ms": 5000,
        "cache_ttl_seconds": 60,
        "batch_size": 100,
        "retry_interval_ms": 100
      },
      "baseline_decision": null,
      "created_at": "2026-07-16T14:16:00+00:00"
    },
    {
      "id": "23a106ea-6bf5-4749-b914-af19223bde7d",
      "run_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "iteration_number": 4,
      "config_applied": {
        "pool_size": 25,
        "query_timeout_ms": 5000,
        "cache_ttl_seconds": 300,
        "batch_size": 100,
        "retry_interval_ms": 100
      },
      "metrics": {
        "p95_latency_ms": 285,
        "p99_latency_ms": 410,
        "throughput_rps": 88.6,
        "error_rate": 0.001,
        "avg_latency_ms": 185.2,
        "median_latency_ms": 156.8,
        "request_count": 5316,
        "failure_count": 5
      },
      "judge_analysis": {
        "bottleneck": "query_latency",
        "severity": "medium",
        "trend": "improving",
        "reasoning": "Cache TTL increase reduced repeated scan latency significantly. Remaining p95 is driven by slow individual order-detail queries — query_timeout is overly generous at 5000ms, masking slow-query detection.",
        "recommended_direction": {
          "query_timeout_ms": "decrease",
          "batch_size": "increase"
        }
      },
      "judge_vision_analysis": {
        "visual_insight": "Vision analysis unavailable",
        "error": "No serverless vision model available on Fireworks as of Jul 2026"
      },
      "optimizer_proposal": {
        "proposed_config": {
          "pool_size": 25,
          "query_timeout_ms": 4500,
          "cache_ttl_seconds": 300,
          "batch_size": 150,
          "retry_interval_ms": 100
        },
        "rationale": "Primary action: query timeout ms — decrease. Cache TTL increase reduced repeated scan latency significantly. Remaining p95 is...",
        "expected_effect": "Target p95 reduction of 10–20% based on bottleneck type and prior iteration delta.",
        "confidence": "medium"
      },
      "veto_event": null,
      "final_decision": {
        "pool_size": 25,
        "query_timeout_ms": 5000,
        "cache_ttl_seconds": 300,
        "batch_size": 100,
        "retry_interval_ms": 100
      },
      "baseline_decision": null,
      "created_at": "2026-07-16T14:24:00+00:00"
    },
    {
      "id": "49f71f74-461e-489b-b7c3-d6d6133f4e17",
      "run_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "iteration_number": 5,
      "config_applied": {
        "pool_size": 25,
        "query_timeout_ms": 2000,
        "cache_ttl_seconds": 300,
        "batch_size": 150,
        "retry_interval_ms": 100
      },
      "metrics": {
        "p95_latency_ms": 225,
        "p99_latency_ms": 315,
        "throughput_rps": 94.1,
        "error_rate": 0.002,
        "avg_latency_ms": 146.2,
        "median_latency_ms": 123.8,
        "request_count": 5646,
        "failure_count": 11
      },
      "judge_analysis": {
        "bottleneck": "query_latency",
        "severity": "low",
        "trend": "improving",
        "reasoning": "Tightened timeout and larger batch size improved order-create throughput. P95 now in the 200-250ms range. Minor oscillation visible — retry_interval slightly high, causing retry storms under marginal latency.",
        "recommended_direction": {
          "retry_interval_ms": "decrease",
          "pool_size": "increase"
        }
      },
      "judge_vision_analysis": {
        "visual_insight": "Vision analysis unavailable",
        "error": "No serverless vision model available on Fireworks as of Jul 2026"
      },
      "optimizer_proposal": {
        "proposed_config": {
          "pool_size": 30,
          "query_timeout_ms": 2000,
          "cache_ttl_seconds": 300,
          "batch_size": 150,
          "retry_interval_ms": 75
        },
        "rationale": "Primary action: retry interval ms — decrease. Tightened timeout and larger batch size improved order-create throughput. P95 no...",
        "expected_effect": "Target p95 reduction of 10–20% based on bottleneck type and prior iteration delta.",
        "confidence": "medium"
      },
      "veto_event": null,
      "final_decision": {
        "pool_size": 25,
        "query_timeout_ms": 2000,
        "cache_ttl_seconds": 300,
        "batch_size": 150,
        "retry_interval_ms": 100
      },
      "baseline_decision": null,
      "created_at": "2026-07-16T14:32:00+00:00"
    },
    {
      "id": "2c1e617d-3060-4ac9-9a15-a6717d391077",
      "run_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "iteration_number": 6,
      "config_applied": {
        "pool_size": 30,
        "query_timeout_ms": 2000,
        "cache_ttl_seconds": 300,
        "batch_size": 150,
        "retry_interval_ms": 50
      },
      "metrics": {
        "p95_latency_ms": 198,
        "p99_latency_ms": 275,
        "throughput_rps": 97.3,
        "error_rate": 0.001,
        "avg_latency_ms": 128.7,
        "median_latency_ms": 108.9,
        "request_count": 5838,
        "failure_count": 6
      },
      "judge_analysis": {
        "bottleneck": "query_latency",
        "severity": "low",
        "trend": "improving",
        "reasoning": "Reduced retry interval cut storm amplification. Pool at 30 providing good coverage. P95 approaching target. Fine-tune: cache TTL could be extended further for product-search stability.",
        "recommended_direction": {
          "cache_ttl_seconds": "increase",
          "query_timeout_ms": "decrease"
        }
      },
      "judge_vision_analysis": {
        "visual_insight": "Vision analysis unavailable",
        "error": "No serverless vision model available on Fireworks as of Jul 2026"
      },
      "optimizer_proposal": {
        "proposed_config": {
          "pool_size": 30,
          "query_timeout_ms": 1500,
          "cache_ttl_seconds": 600,
          "batch_size": 150,
          "retry_interval_ms": 50
        },
        "rationale": "Primary action: cache ttl seconds — increase. Reduced retry interval cut storm amplification. Pool at 30 providing good covera...",
        "expected_effect": "Target p95 reduction of 10–20% based on bottleneck type and prior iteration delta.",
        "confidence": "medium"
      },
      "veto_event": null,
      "final_decision": {
        "pool_size": 30,
        "query_timeout_ms": 2000,
        "cache_ttl_seconds": 300,
        "batch_size": 150,
        "retry_interval_ms": 50
      },
      "baseline_decision": null,
      "created_at": "2026-07-16T14:40:00+00:00"
    },
    {
      "id": "4a419589-24b1-4b5b-a0f6-0ded817bca33",
      "run_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "iteration_number": 7,
      "config_applied": {
        "pool_size": 30,
        "query_timeout_ms": 1500,
        "cache_ttl_seconds": 600,
        "batch_size": 150,
        "retry_interval_ms": 50
      },
      "metrics": {
        "p95_latency_ms": 174,
        "p99_latency_ms": 238,
        "throughput_rps": 99.8,
        "error_rate": 0.0,
        "avg_latency_ms": 113.1,
        "median_latency_ms": 95.7,
        "request_count": 5988,
        "failure_count": 0
      },
      "judge_analysis": {
        "bottleneck": "stable",
        "severity": "low",
        "trend": "stable",
        "reasoning": "System stable at 174ms p95, well below target. Throughput peaked at 99.8 RPS. Cache TTL at 600s serving most product-search from memory. No clear further bottleneck — marginal gains only.",
        "recommended_direction": {
          "cache_ttl_seconds": "maintain",
          "pool_size": "maintain"
        }
      },
      "judge_vision_analysis": {
        "visual_insight": "Vision analysis unavailable",
        "error": "No serverless vision model available on Fireworks as of Jul 2026"
      },
      "optimizer_proposal": {
        "proposed_config": {
          "pool_size": 30,
          "query_timeout_ms": 1500,
          "cache_ttl_seconds": 600,
          "batch_size": 150,
          "retry_interval_ms": 50
        },
        "rationale": "Primary action: cache ttl seconds — maintain. System stable at 174ms p95, well below target. Throughput peaked at 99.8 RPS. Ca...",
        "expected_effect": "Target p95 reduction of 10–20% based on bottleneck type and prior iteration delta.",
        "confidence": "medium"
      },
      "veto_event": null,
      "final_decision": {
        "pool_size": 30,
        "query_timeout_ms": 1500,
        "cache_ttl_seconds": 600,
        "batch_size": 150,
        "retry_interval_ms": 50
      },
      "baseline_decision": null,
      "created_at": "2026-07-16T14:48:00+00:00"
    },
    {
      "id": "6fc6bca2-5b98-4640-a4c8-d86fb7ab5c0c",
      "run_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "iteration_number": 8,
      "config_applied": {
        "pool_size": 30,
        "query_timeout_ms": 1500,
        "cache_ttl_seconds": 600,
        "batch_size": 150,
        "retry_interval_ms": 50
      },
      "metrics": {
        "p95_latency_ms": 158,
        "p99_latency_ms": 218,
        "throughput_rps": 101.4,
        "error_rate": 0.0,
        "avg_latency_ms": 102.7,
        "median_latency_ms": 86.9,
        "request_count": 6084,
        "failure_count": 0
      },
      "judge_analysis": {
        "bottleneck": "stable",
        "severity": "low",
        "trend": "stable",
        "reasoning": "Target achieved: 158ms p95, below 200ms target. Throughput at 101 RPS. All parameters converged. Negligible error rate. Run complete.",
        "recommended_direction": {
          "cache_ttl_seconds": "maintain",
          "pool_size": "maintain"
        }
      },
      "judge_vision_analysis": {
        "visual_insight": "Vision analysis unavailable",
        "error": "No serverless vision model available on Fireworks as of Jul 2026"
      },
      "optimizer_proposal": {
        "proposed_config": {
          "pool_size": 30,
          "query_timeout_ms": 1500,
          "cache_ttl_seconds": 600,
          "batch_size": 150,
          "retry_interval_ms": 50
        },
        "rationale": "Primary action: cache ttl seconds — maintain. Target achieved: 158ms p95, below 200ms target. Throughput at 101 RPS. All param...",
        "expected_effect": "Target p95 reduction of 10–20% based on bottleneck type and prior iteration delta.",
        "confidence": "medium"
      },
      "veto_event": null,
      "final_decision": {
        "pool_size": 30,
        "query_timeout_ms": 1500,
        "cache_ttl_seconds": 600,
        "batch_size": 150,
        "retry_interval_ms": 50
      },
      "baseline_decision": null,
      "created_at": "2026-07-16T14:56:00+00:00"
    }
  ]
};

export const DEMO_BASELINE = {
  "run_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
  "mode": "baseline",
  "status": "finished",
  "termination_reason": "plateau",
  "iterations": [
    {
      "id": "f5765a48-98c3-433d-8a2b-bdfa11a7e60b",
      "run_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "iteration_number": 1,
      "config_applied": {
        "pool_size": 5,
        "query_timeout_ms": 5000,
        "cache_ttl_seconds": 60,
        "batch_size": 100,
        "retry_interval_ms": 100
      },
      "metrics": {
        "p95_latency_ms": 824,
        "p99_latency_ms": 1260,
        "throughput_rps": 42.1,
        "error_rate": 0.045,
        "avg_latency_ms": 535.6,
        "median_latency_ms": 453.2,
        "request_count": 2526,
        "failure_count": 114
      },
      "judge_analysis": null,
      "judge_vision_analysis": null,
      "optimizer_proposal": null,
      "veto_event": null,
      "final_decision": null,
      "baseline_decision": {
        "diagnosis": "p95=824ms. Pool exhaustion dominant bottleneck.",
        "proposed_config": {
          "pool_size": 8,
          "query_timeout_ms": 5000,
          "cache_ttl_seconds": 60,
          "batch_size": 100,
          "retry_interval_ms": 100
        },
        "rationale": "Single-agent: increase pool_size by 3, stabilize other params."
      },
      "created_at": "2026-07-16T15:00:00+00:00"
    },
    {
      "id": "61c54e48-bc81-49b2-a72f-bfb385d5a5b7",
      "run_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "iteration_number": 2,
      "config_applied": {
        "pool_size": 10,
        "query_timeout_ms": 5000,
        "cache_ttl_seconds": 60,
        "batch_size": 100,
        "retry_interval_ms": 100
      },
      "metrics": {
        "p95_latency_ms": 620,
        "p99_latency_ms": 920,
        "throughput_rps": 62.3,
        "error_rate": 0.018,
        "avg_latency_ms": 403.0,
        "median_latency_ms": 341.0,
        "request_count": 3738,
        "failure_count": 67
      },
      "judge_analysis": null,
      "judge_vision_analysis": null,
      "optimizer_proposal": null,
      "veto_event": null,
      "final_decision": null,
      "baseline_decision": {
        "diagnosis": "p95=620ms. Pool exhaustion dominant bottleneck.",
        "proposed_config": {
          "pool_size": 13,
          "query_timeout_ms": 5000,
          "cache_ttl_seconds": 60,
          "batch_size": 100,
          "retry_interval_ms": 100
        },
        "rationale": "Single-agent: increase pool_size by 3, stabilize other params."
      },
      "created_at": "2026-07-16T15:08:00+00:00"
    },
    {
      "id": "d9353f0d-a39a-4c71-bce8-8c19edb369d9",
      "run_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "iteration_number": 3,
      "config_applied": {
        "pool_size": 15,
        "query_timeout_ms": 5000,
        "cache_ttl_seconds": 60,
        "batch_size": 100,
        "retry_interval_ms": 100
      },
      "metrics": {
        "p95_latency_ms": 490,
        "p99_latency_ms": 710,
        "throughput_rps": 71.4,
        "error_rate": 0.008,
        "avg_latency_ms": 318.5,
        "median_latency_ms": 269.5,
        "request_count": 4284,
        "failure_count": 34
      },
      "judge_analysis": null,
      "judge_vision_analysis": null,
      "optimizer_proposal": null,
      "veto_event": null,
      "final_decision": null,
      "baseline_decision": {
        "diagnosis": "p95=490ms. Incremental pool increases still improving but slowing.",
        "proposed_config": {
          "pool_size": 18,
          "query_timeout_ms": 5000,
          "cache_ttl_seconds": 60,
          "batch_size": 100,
          "retry_interval_ms": 100
        },
        "rationale": "Single-agent: increase pool_size by 3, stabilize other params."
      },
      "created_at": "2026-07-16T15:16:00+00:00"
    },
    {
      "id": "9becb2a5-bd2d-4a06-88b1-f0d97bfeece2",
      "run_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "iteration_number": 4,
      "config_applied": {
        "pool_size": 18,
        "query_timeout_ms": 5000,
        "cache_ttl_seconds": 60,
        "batch_size": 100,
        "retry_interval_ms": 100
      },
      "metrics": {
        "p95_latency_ms": 415,
        "p99_latency_ms": 590,
        "throughput_rps": 76.8,
        "error_rate": 0.004,
        "avg_latency_ms": 269.8,
        "median_latency_ms": 228.3,
        "request_count": 4608,
        "failure_count": 18
      },
      "judge_analysis": null,
      "judge_vision_analysis": null,
      "optimizer_proposal": null,
      "veto_event": null,
      "final_decision": null,
      "baseline_decision": {
        "diagnosis": "p95=415ms. Incremental pool increases still improving but slowing.",
        "proposed_config": {
          "pool_size": 21,
          "query_timeout_ms": 5000,
          "cache_ttl_seconds": 120,
          "batch_size": 100,
          "retry_interval_ms": 100
        },
        "rationale": "Single-agent: increase pool_size by 3, stabilize other params."
      },
      "created_at": "2026-07-16T15:24:00+00:00"
    },
    {
      "id": "bfaf3b38-9d92-47dd-a761-b6fadff6021b",
      "run_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "iteration_number": 5,
      "config_applied": {
        "pool_size": 20,
        "query_timeout_ms": 5000,
        "cache_ttl_seconds": 120,
        "batch_size": 100,
        "retry_interval_ms": 100
      },
      "metrics": {
        "p95_latency_ms": 380,
        "p99_latency_ms": 540,
        "throughput_rps": 79.2,
        "error_rate": 0.003,
        "avg_latency_ms": 247.0,
        "median_latency_ms": 209.0,
        "request_count": 4752,
        "failure_count": 14
      },
      "judge_analysis": null,
      "judge_vision_analysis": null,
      "optimizer_proposal": null,
      "veto_event": null,
      "final_decision": null,
      "baseline_decision": {
        "diagnosis": "p95=380ms. Incremental pool increases still improving but slowing.",
        "proposed_config": {
          "pool_size": 23,
          "query_timeout_ms": 5000,
          "cache_ttl_seconds": 120,
          "batch_size": 100,
          "retry_interval_ms": 100
        },
        "rationale": "Single-agent: increase pool_size by 3, stabilize other params."
      },
      "created_at": "2026-07-16T15:32:00+00:00"
    },
    {
      "id": "1bf2b262-f5c3-4d83-920f-a8c3d1753459",
      "run_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "iteration_number": 6,
      "config_applied": {
        "pool_size": 22,
        "query_timeout_ms": 5000,
        "cache_ttl_seconds": 120,
        "batch_size": 100,
        "retry_interval_ms": 100
      },
      "metrics": {
        "p95_latency_ms": 360,
        "p99_latency_ms": 510,
        "throughput_rps": 81.0,
        "error_rate": 0.003,
        "avg_latency_ms": 234.0,
        "median_latency_ms": 198.0,
        "request_count": 4860,
        "failure_count": 15
      },
      "judge_analysis": null,
      "judge_vision_analysis": null,
      "optimizer_proposal": null,
      "veto_event": null,
      "final_decision": null,
      "baseline_decision": {
        "diagnosis": "p95=360ms. Incremental pool increases still improving but slowing.",
        "proposed_config": {
          "pool_size": 25,
          "query_timeout_ms": 5000,
          "cache_ttl_seconds": 120,
          "batch_size": 100,
          "retry_interval_ms": 100
        },
        "rationale": "Single-agent: increase pool_size by 3, stabilize other params."
      },
      "created_at": "2026-07-16T15:40:00+00:00"
    },
    {
      "id": "68673b66-9b18-4afa-8842-3cb04b33ee05",
      "run_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "iteration_number": 7,
      "config_applied": {
        "pool_size": 22,
        "query_timeout_ms": 5000,
        "cache_ttl_seconds": 120,
        "batch_size": 100,
        "retry_interval_ms": 100
      },
      "metrics": {
        "p95_latency_ms": 345,
        "p99_latency_ms": 495,
        "throughput_rps": 82.1,
        "error_rate": 0.002,
        "avg_latency_ms": 224.2,
        "median_latency_ms": 189.8,
        "request_count": 4926,
        "failure_count": 10
      },
      "judge_analysis": null,
      "judge_vision_analysis": null,
      "optimizer_proposal": null,
      "veto_event": null,
      "final_decision": null,
      "baseline_decision": {
        "diagnosis": "p95=345ms. Incremental pool increases still improving but slowing.",
        "proposed_config": {
          "pool_size": 25,
          "query_timeout_ms": 5000,
          "cache_ttl_seconds": 120,
          "batch_size": 100,
          "retry_interval_ms": 100
        },
        "rationale": "Single-agent: increase pool_size by 3, stabilize other params."
      },
      "created_at": "2026-07-16T15:48:00+00:00"
    },
    {
      "id": "44b8cf14-6b27-4939-82fa-f1b11018d27b",
      "run_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "iteration_number": 8,
      "config_applied": {
        "pool_size": 22,
        "query_timeout_ms": 5000,
        "cache_ttl_seconds": 120,
        "batch_size": 100,
        "retry_interval_ms": 100
      },
      "metrics": {
        "p95_latency_ms": 338,
        "p99_latency_ms": 482,
        "throughput_rps": 82.7,
        "error_rate": 0.002,
        "avg_latency_ms": 219.7,
        "median_latency_ms": 185.9,
        "request_count": 4962,
        "failure_count": 10
      },
      "judge_analysis": null,
      "judge_vision_analysis": null,
      "optimizer_proposal": null,
      "veto_event": null,
      "final_decision": null,
      "baseline_decision": {
        "diagnosis": "p95=338ms. Incremental pool increases still improving but slowing.",
        "proposed_config": {
          "pool_size": 25,
          "query_timeout_ms": 5000,
          "cache_ttl_seconds": 120,
          "batch_size": 100,
          "retry_interval_ms": 100
        },
        "rationale": "Single-agent: increase pool_size by 3, stabilize other params."
      },
      "created_at": "2026-07-16T15:56:00+00:00"
    }
  ]
};

export const DEMO_RUN_LIST = [
  {
    run_id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    mode: "multi_agent",
    status: "finished",
    termination_reason: "target_hit",
    created_at: "2026-07-16T14:00:00+00:00",
    is_demo: true,
  },
  {
    run_id: "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    mode: "baseline",
    status: "finished",
    termination_reason: "plateau",
    created_at: "2026-07-16T15:00:00+00:00",
    is_demo: true,
  },
];

export const DEMO_RUN_MAP = {
  "a1b2c3d4-e5f6-7890-abcd-ef1234567890": DEMO_MULTI_AGENT,
  "b2c3d4e5-f6a7-8901-bcde-f12345678901": DEMO_BASELINE,
};
