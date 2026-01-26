# Example: CR Markdown to prd.json Import

This example demonstrates how Ralph imports tasks from a Change Request (CR) markdown file into the canonical `prd.json` format.

## Source: CR Markdown File

**File:** `changes/CR-API-RATE-LIMITING.md`

```markdown
# CR: API Rate Limiting

**Created:** 2026-01-25
**Status:** Draft
**Scope:** Medium
**Priority:** P2-Normal

## Summary

Implement rate limiting for the public API to prevent abuse and ensure fair usage across all clients.

## Problem Statement

The API currently has no rate limiting, allowing clients to make unlimited requests. This creates risk of:
- Resource exhaustion from aggressive clients
- Denial of service (intentional or accidental)
- Unfair usage patterns affecting other users

## Desired Behavior

- Rate limits configurable per endpoint
- Standard rate limit headers (X-RateLimit-*)
- 429 Too Many Requests response when limit exceeded
- Redis-based distributed rate limiting

## Task List

```json
[
  {
    "id": "CR-RATE-1",
    "category": "setup",
    "description": "Add Redis client and rate limiting dependencies",
    "steps": [
      "Add redis-py to pyproject.toml dependencies",
      "Add python-ratelimit library",
      "Create src/config/redis.py with connection settings",
      "Add REDIS_URL to .env.example",
      "Run `uv run python -c \"import redis\"` - exits with code 0"
    ],
    "passes": false
  },
  {
    "id": "CR-RATE-2",
    "category": "backend",
    "description": "Create rate limiting middleware",
    "steps": [
      "Create src/middleware/rate_limit.py",
      "Implement RateLimitMiddleware class",
      "Support configurable limits per route pattern",
      "Add rate limit headers to responses",
      "Run `uv run pytest tests/middleware/test_rate_limit.py -v` - exits with code 0"
    ],
    "passes": false
  },
  {
    "id": "CR-RATE-3",
    "category": "backend",
    "description": "Implement Redis-based rate counter",
    "steps": [
      "Create src/services/rate_counter.py",
      "Implement sliding window rate counting",
      "Support distributed counting across instances",
      "Add TTL-based automatic cleanup",
      "Run `uv run pytest tests/services/test_rate_counter.py -v` - exits with code 0"
    ],
    "passes": false
  },
  {
    "id": "CR-RATE-4",
    "category": "feature",
    "description": "Configure rate limits for API endpoints",
    "steps": [
      "Add rate_limits section to ralph.yml",
      "Define limits: /api/query 10/min, /api/ingest 5/min, /api/health unlimited",
      "Apply middleware to FastAPI app",
      "Verify limits work in dev environment"
    ],
    "passes": false
  },
  {
    "id": "CR-RATE-5",
    "category": "testing",
    "description": "Add integration tests for rate limiting",
    "steps": [
      "Create tests/integration/test_rate_limiting.py",
      "Test rate limit enforcement",
      "Test rate limit headers",
      "Test 429 response format",
      "Test rate limit reset after window",
      "Run `uv run pytest tests/integration/test_rate_limiting.py -v` - exits with code 0"
    ],
    "passes": false
  },
  {
    "id": "CR-RATE-6",
    "category": "documentation",
    "description": "Document rate limiting for API consumers",
    "steps": [
      "Add Rate Limiting section to API docs",
      "Document rate limit headers",
      "Add examples of handling 429 responses",
      "Update README with rate limit configuration"
    ],
    "passes": false
  }
]
```

## References

- [Token Bucket Algorithm](https://en.wikipedia.org/wiki/Token_bucket)
- [FastAPI Middleware](https://fastapi.tiangolo.com/tutorial/middleware/)
```

---

## Import Command

```bash
ralph import --cr changes/CR-API-RATE-LIMITING.md
```

---

## Output: prd.json

**File:** `.ralph/prd.json`

```json
{
  "$schema": "https://ralph-orchestrator.dev/schemas/prd.schema.json",
  "project": "API Rate Limiting",
  "branchName": "ralph/api-rate-limiting",
  "description": "Implement rate limiting for the public API to prevent abuse and ensure fair usage across all clients.",
  "tasks": [
    {
      "id": "T-001",
      "title": "Add Redis client and rate limiting dependencies",
      "description": "Add Redis client and rate limiting dependencies",
      "acceptanceCriteria": [
        "Add redis-py to pyproject.toml dependencies",
        "Add python-ratelimit library",
        "Create src/config/redis.py with connection settings",
        "Add REDIS_URL to .env.example",
        "Run `uv run python -c \"import redis\"` - exits with code 0"
      ],
      "priority": 1,
      "passes": false,
      "notes": "Imported from CR-RATE-1 (category: setup)"
    },
    {
      "id": "T-002",
      "title": "Create rate limiting middleware",
      "description": "Create rate limiting middleware",
      "acceptanceCriteria": [
        "Create src/middleware/rate_limit.py",
        "Implement RateLimitMiddleware class",
        "Support configurable limits per route pattern",
        "Add rate limit headers to responses",
        "Run `uv run pytest tests/middleware/test_rate_limit.py -v` - exits with code 0"
      ],
      "priority": 2,
      "passes": false,
      "notes": "Imported from CR-RATE-2 (category: backend)"
    },
    {
      "id": "T-003",
      "title": "Implement Redis-based rate counter",
      "description": "Implement Redis-based rate counter",
      "acceptanceCriteria": [
        "Create src/services/rate_counter.py",
        "Implement sliding window rate counting",
        "Support distributed counting across instances",
        "Add TTL-based automatic cleanup",
        "Run `uv run pytest tests/services/test_rate_counter.py -v` - exits with code 0"
      ],
      "priority": 3,
      "passes": false,
      "notes": "Imported from CR-RATE-3 (category: backend)"
    },
    {
      "id": "T-004",
      "title": "Configure rate limits for API endpoints",
      "description": "Configure rate limits for API endpoints",
      "acceptanceCriteria": [
        "Add rate_limits section to ralph.yml",
        "Define limits: /api/query 10/min, /api/ingest 5/min, /api/health unlimited",
        "Apply middleware to FastAPI app",
        "Verify limits work in dev environment"
      ],
      "priority": 4,
      "passes": false,
      "notes": "Imported from CR-RATE-4 (category: feature)"
    },
    {
      "id": "T-005",
      "title": "Add integration tests for rate limiting",
      "description": "Add integration tests for rate limiting",
      "acceptanceCriteria": [
        "Create tests/integration/test_rate_limiting.py",
        "Test rate limit enforcement",
        "Test rate limit headers",
        "Test 429 response format",
        "Test rate limit reset after window",
        "Run `uv run pytest tests/integration/test_rate_limiting.py -v` - exits with code 0"
      ],
      "priority": 5,
      "passes": false,
      "notes": "Imported from CR-RATE-5 (category: testing)"
    },
    {
      "id": "T-006",
      "title": "Document rate limiting for API consumers",
      "description": "Document rate limiting for API consumers",
      "acceptanceCriteria": [
        "Add Rate Limiting section to API docs",
        "Document rate limit headers",
        "Add examples of handling 429 responses",
        "Update README with rate limit configuration"
      ],
      "priority": 6,
      "passes": false,
      "notes": "Imported from CR-RATE-6 (category: documentation)"
    }
  ]
}
```

---

## Transformation Summary

| CR Field | prd.json Field | Transformation Applied |
|----------|----------------|------------------------|
| `id: "CR-RATE-1"` | `id: "T-001"` | Normalized to T-NNN format |
| `description` | `title` | Used as-is (under 100 chars) |
| `description` | `description` | Copied unchanged |
| `steps[]` | `acceptanceCriteria[]` | Direct mapping |
| `category: "setup"` | `notes` | Preserved in notes field |
| `passes: false` | `passes: false` | Direct mapping |
| (array position) | `priority: 1` | Assigned from order |

### Metadata Extraction

| Source | Target |
|--------|--------|
| `# CR: API Rate Limiting` | `project: "API Rate Limiting"` |
| `## Summary` first paragraph | `description` |
| Filename: `CR-API-RATE-LIMITING.md` | `branchName: "ralph/api-rate-limiting"` |

---

## Notes

1. **ID Normalization**: Original CR IDs (`CR-RATE-1`, etc.) are converted to the canonical `T-NNN` format. The original ID is preserved in the `notes` field for traceability.

2. **Category Preservation**: The `category` field from CR format is not lost—it's included in the `notes` field and can be used for filtering or reporting.

3. **Priority Assignment**: Priorities are assigned sequentially based on the order in the original CR file. Use `--group-by-category` flag to group by category instead.

4. **Round-Trip**: You can export this prd.json back to CR markdown format using `ralph export --format cr`, though some metadata (like `category`) will be inferred rather than preserved exactly.
