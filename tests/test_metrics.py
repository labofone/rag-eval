import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Assuming your FastAPI app instance is named 'app' in 'app.main'
from app.main import app
from app.dependencies import validate_api_key
from app.schemas.metric import MetricRecommendationRequest, MetricRecommendationResponse

# --- Test Setup ---

# Override the API key dependency for testing
async def override_validate_api_key():
    return {"api_key": "test-key"}

app.dependency_overrides[validate_api_key] = override_validate_api_key

client = TestClient(app)

# --- Mocking ---

# Mock Redis globally for most tests in this module
# We patch 'app.services.metric_recommendation.redis'
@pytest.fixture(autouse=True)
def mock_redis():
    with patch('app.services.metric_recommendation.redis') as mock_redis_client:
        # Configure the mock behavior (e.g., get returns None, set does nothing)
        mock_redis_client.get.return_value = None
        mock_redis_client.set.return_value = True
        yield mock_redis_client

# Mock LLM function globally (returns empty list as per current implementation)
@pytest.fixture(autouse=True)
def mock_llm():
     # Patch 'app.services.metric_recommendation.get_llm_recommendation'
    with patch('app.services.metric_recommendation.get_llm_recommendation') as mock_llm_func:
        mock_llm_func.return_value = [] # Coroutine should return awaitable
        yield mock_llm_func


# --- Test Cases ---

# Section 1: API Contract & Schema Validation

@pytest.mark.parametrize(
    "payload",
    [
        {"query": "test query"},
        {"query": "test query", "use_case": "test_case"},
        {"query": "test query", "constraints": ["constraint1"]},
        {"query": "test query", "use_case": "test_case", "constraints": ["constraint1", "constraint2"]},
    ],
    ids=[
        "query_only",
        "query_use_case",
        "query_constraints",
        "query_use_case_constraints",
    ]
)
def test_recommend_metrics_valid_requests(payload):
    """ Tests valid request payloads return 200 OK and expected response structure. """
    response = client.post("/metrics/recommend", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "recommended_metrics" in data
    assert isinstance(data["recommended_metrics"], list)
    assert "reasoning" in data
    assert isinstance(data["reasoning"], str)
    assert "confidence" in data
    assert isinstance(data["confidence"], float)
    # Optional fields might not always be present, check type if they are
    if "fallback_metrics" in data and data["fallback_metrics"] is not None:
         assert isinstance(data["fallback_metrics"], list)
    if "warnings" in data and data["warnings"] is not None:
         assert isinstance(data["warnings"], list)


@pytest.mark.parametrize(
    "payload, expected_detail_part",
    [
        ({}, "query"), # Missing query
        ({"query": 123}, "query"), # Invalid query type
        ({"query": "test", "use_case": 123}, "use_case"), # Invalid use_case type
        ({"query": "test", "constraints": "not-a-list"}, "constraints"), # Invalid constraints type
        ({"query": "test", "constraints": [1, 2, 3]}, "constraints"), # Invalid item type in constraints
    ],
    ids=[
        "missing_query",
        "invalid_query_type",
        "invalid_use_case_type",
        "invalid_constraints_type",
        "invalid_constraints_item_type",
    ]
)
def test_recommend_metrics_invalid_requests(payload, expected_detail_part):
    """ Tests invalid request payloads return 422 Unprocessable Entity. """
    response = client.post("/metrics/recommend", json=payload)
    assert response.status_code == 422
    # Check if the specific field is mentioned in the error detail
    error_details = response.json().get("detail", [])
    assert any(expected_detail_part in str(err.get("loc", "")) for err in error_details)


# Section 2: Rule-Based Engine Unit Tests

# Import the function to test directly
from app.services.metric_recommendation import get_rule_based_metrics, RULES

# Test data for rule-based logic
# Format: (query, use_case, expected_metrics, expected_confidence)
rule_test_cases = [
    # Keyword matching
    ("I need factual accuracy", None, ["faithfulness", "answer_correctness"], 0.66),
    ("How about speed?", None, ["latency@k", "tokens_per_second"], 0.66),
    ("Ensure diversity in results", None, ["diversity@k", "semantic_variety"], 0.66),
    # Case insensitivity
    ("check FACTUAL data", None, ["faithfulness", "answer_correctness"], 0.66),
    # Multiple keywords
    ("Need factual results with speed", None, ["faithfulness", "answer_correctness", "latency@k", "tokens_per_second"], 1.0), # Confidence capped at 1.0
    # No matching keywords
    ("General query about relevance", None, [], 0.0),
    # Use case matching (assuming 'legal' might be added to RULES later)
    # To make this test pass now, we temporarily add 'legal' to RULES for this test's scope if needed,
    # or we can test the logic path assuming it exists. Let's test the path.
    # If 'legal' is not in RULES, it should behave like no match.
    ("A query", "legal", [], 0.0), # Assuming 'legal' not in current RULES
    # Keyword and use case (assuming 'legal' not in RULES)
    ("Factual query", "legal", ["faithfulness", "answer_correctness"], 0.66),
    # Duplicate handling (speed keyword + speed keyword)
    ("speed speed speed", None, ["latency@k", "tokens_per_second"], 0.66), # Should be deduplicated
]

@pytest.mark.parametrize(
    "query, use_case, expected_metrics, expected_confidence",
    rule_test_cases,
    ids=[
        "factual_keyword",
        "speed_keyword",
        "diversity_keyword",
        "case_insensitive",
        "multiple_keywords",
        "no_match",
        "use_case_no_match",
        "keyword_and_use_case_no_match",
        "duplicates",
    ]
)
def test_get_rule_based_metrics(query, use_case, expected_metrics, expected_confidence):
    """ Tests the rule-based metric extraction logic directly. """
    # Note: If testing a use_case that *should* exist, you might need to patch RULES
    # For now, we test based on the current RULES definition in the service file.
    metrics, confidence = get_rule_based_metrics(query, use_case)

    # Sort lists to ensure order doesn't affect comparison
    assert sorted(metrics) == sorted(expected_metrics)
    # Use pytest.approx for float comparison
    assert confidence == pytest.approx(expected_confidence)


# Section 3: LLM Fallback Logic Tests

# We need to patch the LLM function specifically for these tests
# The global mock_llm fixture might interfere, so we use patch directly here.
# We also need the mock_redis fixture to be active.

@pytest.mark.asyncio
async def test_llm_fallback_triggered_when_low_confidence(mock_redis):
    """ Verify LLM is called when rule confidence is low (< 0.7). """
    payload = {"query": "very niche query with no keywords"} # Expect confidence 0.0
    with patch('app.services.metric_recommendation.get_llm_recommendation', new_callable=MagicMock) as mock_llm_func:
        # Simulate LLM returning some metrics
        mock_llm_func.return_value = ["llm_metric_1", "llm_metric_2"]

        response = client.post("/metrics/recommend", json=payload)

        assert response.status_code == 200
        mock_llm_func.assert_called_once_with(payload["query"]) # Check LLM was called
        data = response.json()
        # Check LLM metrics are included and confidence is boosted
        assert "llm_metric_1" in data["recommended_metrics"]
        assert "llm_metric_2" in data["recommended_metrics"]
        assert data["confidence"] == pytest.approx(0.8)

@pytest.mark.asyncio
async def test_llm_fallback_not_triggered_when_high_confidence(mock_redis):
    """ Verify LLM is NOT called when rule confidence is high (>= 0.7). """
    # This query triggers two keywords -> confidence 0.66 * 2 = 1.32 -> capped at 1.0
    payload = {"query": "factual speed check"}
    with patch('app.services.metric_recommendation.get_llm_recommendation', new_callable=MagicMock) as mock_llm_func:
        mock_llm_func.return_value = ["should_not_be_returned"] # Simulate LLM return

        response = client.post("/metrics/recommend", json=payload)

        assert response.status_code == 200
        mock_llm_func.assert_not_called() # Check LLM was NOT called
        data = response.json()
        # Check only rule metrics are present and confidence is from rules
        assert "should_not_be_returned" not in data["recommended_metrics"]
        assert "faithfulness" in data["recommended_metrics"]
        assert "latency@k" in data["recommended_metrics"]
        assert data["confidence"] == pytest.approx(1.0) # Confidence from rules (0.33 * 4 -> 1.0)

@pytest.mark.asyncio
async def test_llm_fallback_metric_combination_and_deduplication(mock_redis):
    """ Verify LLM metrics are combined correctly with rule metrics and deduplicated. """
    # Query triggers 'speed' (conf 0.66), so LLM should be called
    payload = {"query": "query about speed"}
    with patch('app.services.metric_recommendation.get_llm_recommendation', new_callable=MagicMock) as mock_llm_func:
        # Simulate LLM returning one overlapping metric and one new one
        mock_llm_func.return_value = ["latency@k", "llm_specific_metric"]

        response = client.post("/metrics/recommend", json=payload)

        assert response.status_code == 200
        mock_llm_func.assert_called_once_with(payload["query"])
        data = response.json()

        expected_metrics = ["latency@k", "tokens_per_second", "llm_specific_metric"]
        assert sorted(data["recommended_metrics"]) == sorted(expected_metrics)
        # Check confidence is boosted
        assert data["confidence"] == pytest.approx(0.8)
        # Ensure 'latency@k' appears only once
        assert data["recommended_metrics"].count("latency@k") == 1


# Section 4: Integration Tests (Caching, Error Handling)

# Note: mock_redis fixture is already applied globally via autouse=True

def test_caching_stores_response(mock_redis):
    """ Verify that a successful response is stored in Redis cache. """
    payload = {"query": "cache this factual query"}
    response = client.post("/metrics/recommend", json=payload)
    assert response.status_code == 200

    # Check that redis.set was called (mock_redis is the MagicMock instance)
    mock_redis.set.assert_called_once()
    # Optional: Check arguments passed to set (key generation might be complex)
    args, kwargs = mock_redis.set.call_args
    assert isinstance(args[0], str) # cache_key should be a string
    assert "recommended_metrics" in args[1] # Check if response data is in the value being set
    assert "ex" in kwargs # Check expiry is being set


def test_caching_returns_cached_response(mock_redis):
    """ Verify that a cached response is returned on subsequent identical requests. """
    payload = {"query": "get this from cache factual"}
    cached_data = {
        "recommended_metrics": ["cached_metric"],
        "reasoning": "This came from cache",
        "confidence": 0.99,
        "fallback_metrics": ["cached_fallback"]
    }
    # Configure mock_redis.get to return the cached data for this specific test
    import json
    mock_redis.get.return_value = json.dumps(cached_data)

    # First call (should hit cache)
    response1 = client.post("/metrics/recommend", json=payload)
    assert response1.status_code == 200
    assert response1.json() == cached_data
    mock_redis.get.assert_called_once() # Verify get was called
    mock_redis.set.assert_not_called() # Verify set was NOT called (cache hit)

    # Reset mock for second call if needed, or just check calls
    mock_redis.get.reset_mock()

    # Second call (should also hit cache)
    response2 = client.post("/metrics/recommend", json=payload)
    assert response2.status_code == 200
    assert response2.json() == cached_data
    mock_redis.get.assert_called_once() # Verify get was called again


def test_error_handling_returns_fallback(mock_redis):
    """ Verify that a generic exception returns the default fallback response. """
    payload = {"query": "this will cause an error"}

    # Patch the rule function to raise an exception
    with patch('app.services.metric_recommendation.get_rule_based_metrics') as mock_rules:
        mock_rules.side_effect = Exception("Something went wrong!")

        response = client.post("/metrics/recommend", json=payload)
        assert response.status_code == 200 # Endpoint handles the exception internally

        data = response.json()
        assert data["recommended_metrics"] == ["answer_relevance"]
        assert data["reasoning"] == "Default fallback metrics"
        assert data["confidence"] == pytest.approx(0.1)

        # Ensure cache was not written to on error
        mock_redis.set.assert_not_called()
