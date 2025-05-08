"""
Tests for the buildDataset feature.
"""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from app.build_dataset.schemas import InitialSearchResult, FullContentData, ProcessedContent
from app.build_dataset.processors import calculate_weighted_quality_score, rank_initial_results, convert_content_to_markdown # UPDATED
from app.build_dataset.tools import search_academic_papers_serpapi, download_pdf_async, fetch_webpage_content # UPDATED
from app.build_dataset.storage import upload_raw_artifact, store_processed_content # UPDATED
from app.build_dataset.graph import build_data_collection_graph, GraphState # Import for graph testing if needed

# --- Tests for Schemas ---

def test_initial_search_result_schema():
    """Test the InitialSearchResult schema."""
    data = {
        "link": "https://example.com/paper",
        "title": "Test Paper",
        "snippet": "This is a test snippet.",
        "source_name": "Test Journal",
        "publication_date_str": "2023-01-01",
        "raw_serpapi_data": {"some": "data"},
        "quality_score": 0.8
    }
    result = InitialSearchResult(**data)
    assert result.link == "https://example.com/paper"
    assert result.title == "Test Paper"
    assert result.quality_score == 0.8

def test_full_content_data_schema():
    """Test the FullContentData schema."""
    initial_result = InitialSearchResult(link="https://example.com/paper")
    data = {
        "source_url": "https://example.com/paper",
        "original_metadata": initial_result,
        "raw_content": "Full content text.",
        "content_type": "html",
        "download_successful": True,
        "error_message": None
    }
    content_data = FullContentData(**data)
    assert content_data.source_url == "https://example.com/paper"
    assert content_data.raw_content == "Full content text."

def test_processed_content_schema():
    """Test the ProcessedContent schema."""
    initial_result = InitialSearchResult(link="https://example.com/paper")
    data = {
        "source_url": "https://example.com/paper",
        "original_metadata": initial_result,
        "title": "Processed Title",
        "full_text_markdown": "# Processed Content\nText.",
        "gcs_storage_link": "https://storage.googleapis.com/bucket/blob"
    }
    processed = ProcessedContent(**data)
    assert processed.title == "Processed Title"
    assert processed.full_text_markdown.startswith("# Processed Content")
    assert processed.gcs_storage_link == "https://storage.googleapis.com/bucket/blob"

# --- Tests for Processors ---

@patch('app.build_dataset.processors.datetime')
def test_calculate_weighted_quality_score_recency(mock_datetime):
    """Test quality score calculation, focusing on recency."""
    # Mock current year to control recency calculation
    mock_datetime.now.return_value = datetime(2025, 1, 1)

    # Recent paper (2024)
    recent_result = InitialSearchResult(
        link="http://example.com/recent",
        title="Recent RAG Evaluation",
        snippet="New methods.",
        source_name="arxiv.org",
        publication_date_str="2024",
        original_metadata=MagicMock(research_topic="RAG evaluation") # Mock original_metadata
    )
    score_recent = calculate_weighted_quality_score(recent_result)

    # Older paper (2015) - should have lower recency score
    older_result = InitialSearchResult(
        link="http://example.com/older",
        title="Old RAG Paper",
        snippet="Early methods.",
        source_name="arxiv.org",
        publication_date_str="2015",
        original_metadata=MagicMock(research_topic="RAG evaluation")
    )
    score_older = calculate_weighted_quality_score(older_result)

    # Very old paper (2000) - should have recency score close to 0
    very_old_result = InitialSearchResult(
        link="http://example.com/very_old",
        title="Ancient Paper",
        snippet="Very old stuff.",
        source_name="arxiv.org",
        publication_date_str="2000",
        original_metadata=MagicMock(research_topic="RAG evaluation")
    )
    score_very_old = calculate_weighted_quality_score(very_old_result)

    assert score_recent > score_older
    assert score_older > score_very_old
    assert score_very_old >= 0 # Score should not be negative

@patch('app.build_dataset.processors.datetime')
def test_calculate_weighted_quality_score_relevance(mock_datetime):
    """Test quality score calculation, focusing on relevance."""
    mock_datetime.now.return_value = datetime(2025, 1, 1)

    # Highly relevant (topic in title and snippet)
    relevant_result = InitialSearchResult(
        link="http://example.com/relevant",
        title="RAG Evaluation: New Approaches",
        snippet="This paper discusses RAG evaluation techniques.",
        source_name="arxiv.org",
        publication_date_str="2024",
        original_metadata=MagicMock(research_topic="RAG evaluation")
    )
    score_relevant = calculate_weighted_quality_score(relevant_result)

    # Less relevant (topic only in snippet)
    less_relevant_result = InitialSearchResult(
        link="http://example.com/less_relevant",
        title="New Approaches in NLP",
        snippet="Includes a section on RAG evaluation.",
        source_name="arxiv.org",
        publication_date_str="2024",
        original_metadata=MagicMock(research_topic="RAG evaluation")
    )
    score_less_relevant = calculate_weighted_quality_score(less_relevant_result)

    # Not relevant (topic not in title or snippet)
    not_relevant_result = InitialSearchResult(
        link="http://example.com/not_relevant",
        title="About Cats",
        snippet="This paper is about feline behavior.",
        source_name="arxiv.org",
        publication_date_str="2024",
        original_metadata=MagicMock(research_topic="RAG evaluation")
    )
    score_not_relevant = calculate_weighted_quality_score(not_relevant_result)

    assert score_relevant > score_less_relevant
    assert score_less_relevant > score_not_relevant

@patch('app.build_dataset.processors.datetime')
def test_calculate_weighted_quality_score_source_authority(mock_datetime):
    """Test quality score calculation, focusing on source authority."""
    mock_datetime.now.return_value = datetime(2025, 1, 1)

    # High authority source
    high_auth_result = InitialSearchResult(
        link="http://example.com/high_auth",
        title="RAG Evaluation",
        snippet="Snippet.",
        source_name="arxiv.org",
        publication_date_str="2024",
        original_metadata=MagicMock(research_topic="RAG evaluation")
    )
    score_high_auth = calculate_weighted_quality_score(high_auth_result)

    # Medium authority source
    medium_auth_result = InitialSearchResult(
        link="http://example.com/medium_auth",
        title="RAG Evaluation",
        snippet="Snippet.",
        source_name="ResearchGate",
        publication_date_str="2024",
        original_metadata=MagicMock(research_topic="RAG evaluation")
    )
    score_medium_auth = calculate_weighted_quality_score(medium_auth_result)

    # Low authority source
    low_auth_result = InitialSearchResult(
        link="http://example.com/low_auth",
        title="RAG Evaluation",
        snippet="Snippet.",
        source_name="Personal Blog",
        publication_date_str="2024",
        original_metadata=MagicMock(research_topic="RAG evaluation")
    )
    score_low_auth = calculate_weighted_quality_score(low_auth_result)

    assert score_high_auth > score_medium_auth
    assert score_medium_auth > score_low_auth

@patch('app.build_dataset.processors.calculate_weighted_quality_score')
def test_rank_initial_results(mock_calculate_score):
    """Test the ranking function."""
    # Mock the scoring function to return predictable scores
    mock_calculate_score.side_effect = [0.9, 0.7, 0.5, 0.8, 0.6] # Scores for 5 results

    results = [
        InitialSearchResult(link="http://ex.com/p1", title="Paper 1"),
        InitialSearchResult(link="http://ex.com/p2", title="Paper 2"),
        InitialSearchResult(link="http://ex.com/p3", title="Paper 3"),
        InitialSearchResult(link="http://ex.com/p4", title="Paper 4"),
        InitialSearchResult(link="http://ex.com/p5", title="Paper 5"),
    ]

    # Rank and select top 3
    top_n = 3
    ranked = rank_initial_results(results, top_n=top_n)

    assert len(ranked) == top_n
    # Check if results are sorted by the mocked scores (descending)
    assert ranked[0].quality_score == 0.9
    assert ranked[1].quality_score == 0.8
    assert ranked[2].quality_score == 0.7

    # Test with empty list
    assert rank_initial_results([], top_n=3) == []

@patch('app.build_dataset.processors.MarkItDownConverter') # Mock MarkItDownConverter
def test_convert_content_to_markdown(mock_converter): # UPDATED function name
    """Test the raw content processing function."""
    # Mock the converter instance and its convert method
    mock_instance = MagicMock()
    mock_converter.return_value = mock_instance
    mock_instance.convert.return_value = "# Converted Markdown\nSome text."

    initial_result = InitialSearchResult(
        link="https://example.com/raw",
        title="Original Title",
        snippet="Original snippet.",
        publication_date_str="2023",
        original_metadata=MagicMock(research_topic="test")
    )
    full_content = FullContentData(
        source_url="https://example.com/raw",
        original_metadata=initial_result,
        raw_content="<html><body><h1>Original Title</h1><p>Some raw HTML.</p></body></html>",
        content_type="html",
        download_successful=True
    )

    processed = convert_content_to_markdown(full_content) # UPDATED function call

    assert processed is not None
    assert processed.source_url == "https://example.com/raw"
    assert processed.title == "Original Title" # Currently takes from original_metadata
    assert processed.abstract == "Original snippet." # Currently takes from original_metadata
    assert processed.full_text_markdown == "# Converted Markdown\nSome text." # Expecting mocked output

    # Test with empty raw content
    full_content_empty = FullContentData(
        source_url="https://example.com/empty",
        original_metadata=initial_result,
        raw_content="",
        content_type="html",
        download_successful=True
    )
    processed_empty = convert_content_to_markdown(full_content_empty) # UPDATED function call
    assert processed_empty is None # Should return None if no raw content

# --- Tests for Tools (Basic mocking) ---

@patch('app.build_dataset.tools.GoogleSearch')
@patch('app.build_dataset.tools.settings')
def test_search_academic_papers_serpapi(mock_settings, mock_google_search):
    """Test SerpAPI search tool."""
    mock_settings.SERPAPI_API_KEY = "fake_key"
    mock_search_instance = MagicMock()
    mock_google_search.return_value = mock_search_instance
    mock_search_instance.get_dict.return_value = {
        "organic_results": [
            {"title": "Result 1", "link": "http://link1.com"},
            {"title": "Result 2", "link": "http://link2.com"},
        ]
    }

    results = search_academic_papers_serpapi("test query", num_results=5)

    mock_google_search.assert_called_once_with({
        "engine": "google_scholar",
        "q": "test query",
        "api_key": "fake_key",
        "num": "5",
    })
    assert len(results) == 2
    assert results[0]["title"] == "Result 1"

@patch('app.build_dataset.tools.httpx.AsyncClient')
@patch('app.build_dataset.tools.Path')
async def test_download_pdf_async(mock_path, mock_async_client):
    """Test PDF download tool."""
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None # Simulate success
    mock_response.headers = {"content-type": "application/pdf"}
    mock_response.content = b"fake pdf content"

    mock_client_instance = MagicMock()
    mock_client_instance.get.return_value.__aenter__.return_value = mock_response
    mock_async_client.return_value.__aenter__.return_value = mock_client_instance

    mock_output_dir = MagicMock()
    mock_output_path = MagicMock()
    mock_path.return_value = mock_output_dir
    mock_output_dir.__truediv__.return_value = mock_output_path
    mock_output_path.name = "file.pdf"

    mock_open = MagicMock()
    mock_file_handle = MagicMock()
    mock_open.return_value.__enter__.return_value = mock_file_handle

    with patch('builtins.open', mock_open):
        downloaded_path = await download_pdf_async("http://example.com/file.pdf", mock_output_dir)

    mock_output_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)
    mock_client_instance.get.assert_awaited_once_with("http://example.com/file.pdf")
    mock_open.assert_called_once_with(mock_output_path, "wb")
    mock_file_handle.write.assert_called_once_with(b"fake pdf content")
    assert downloaded_path == mock_output_path

@patch('app.build_dataset.tools.httpx.AsyncClient')
@patch('app.build_dataset.tools.settings')
async def test_fetch_webpage_content(mock_settings, mock_async_client): # UPDATED function name
    """Test Playwright MCP tool wrapper."""
    mock_settings.PLAYWRIGHT_MCP_URL = "http://fake-mcp:8070/extract"

    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None # Simulate success
    mock_response.json.return_value = {"status": "success", "content": "fake webpage content"}

    mock_client_instance = MagicMock()
    mock_client_instance.post.return_value.__aenter__.return_value = mock_response
    mock_async_client.return_value.__aenter__.return_value = mock_client_instance

    content = await fetch_webpage_content("http://example.com/page") # UPDATED function call

    mock_client_instance.post.assert_awaited_once_with(
        "http://fake-mcp:8070/extract",
        json={"url": "http://example.com/page"}
    )
    assert content == "fake webpage content"

# --- Tests for Storage (Basic mocking) ---

@patch('app.build_dataset.storage.storage.Client')
@patch('app.build_dataset.storage.settings')
@patch('app.build_dataset.storage.Path')
def test_upload_raw_artifact(mock_path, mock_settings, mock_storage_client): # UPDATED function name
    """Test GCS upload function."""
    mock_settings.GCS_BUCKET_NAME = "fake-bucket"
    mock_settings.GCS_PROJECT = None 
    mock_settings.GCS_SERVICE_ACCOUNT_FILE = None

    mock_client_instance = MagicMock()
    mock_storage_client.return_value = mock_client_instance

    mock_bucket_instance = MagicMock()
    mock_client_instance.bucket.return_value = mock_bucket_instance

    mock_blob_instance = MagicMock()
    mock_bucket_instance.blob.return_value = mock_blob_instance

    mock_source_file_path = MagicMock()
    mock_source_file_path.exists.return_value = True

    uploaded_url = upload_raw_artifact( # UPDATED function call
        "fake-bucket",
        mock_source_file_path,
        "fake/destination/blob.md"
    )

    mock_storage_client.assert_called_once_with()
    mock_client_instance.bucket.assert_called_once_with("fake-bucket")
    mock_bucket_instance.blob.assert_called_once_with("fake/destination/blob.md")
    mock_blob_instance.upload_from_filename.assert_called_once_with(mock_source_file_path)
    assert uploaded_url == "https://storage.googleapis.com/fake-bucket/fake/destination/blob.md"

@patch('app.build_dataset.storage.upload_raw_artifact') # UPDATED to mock the new function name
@patch('app.build_dataset.storage.Path')
@patch('builtins.open')
def test_store_processed_content(mock_open, mock_path, mock_upload_raw_artifact_func): # UPDATED mock name
    """Test storing processed content."""
    mock_temp_dir = MagicMock()
    mock_path.return_value = mock_temp_dir
    mock_temp_dir.mkdir.return_value = None
    mock_temp_dir.iterdir.return_value = [MagicMock()]

    mock_file_handle = MagicMock()
    mock_open.return_value.__enter__.return_value = mock_file_handle

    mock_upload_raw_artifact_func.side_effect = ["http://gcs.link/file1.md", None] # UPDATED mock name

    dummy_processed_content = [
        ProcessedContent(
            source_url="http://example.com/p1",
            original_metadata=InitialSearchResult(link="http://example.com/p1"),
            full_text_markdown="# Content 1"
        ),
        ProcessedContent(
            source_url="http://example.com/p2",
            original_metadata=InitialSearchResult(link="http://example.com/p2"),
            full_text_markdown="# Content 2"
        ),
    ]

    stored_data = store_processed_content(dummy_processed_content, base_path="test_path")

    assert len(stored_data) == 2
    assert stored_data[0].gcs_storage_link == "http://gcs.link/file1.md"
    assert stored_data[1].gcs_storage_link is None

    mock_temp_dir.iterdir.assert_called()
    mock_temp_dir.iterdir.return_value[0].unlink.assert_called_once()
    mock_temp_dir.rmdir.assert_called_once()

    assert store_processed_content([]) == []

# --- Basic Graph Test (Requires minimal setup) ---

@patch('app.build_dataset.graph.node_fetch_initial_results')
@patch('app.build_dataset.graph.node_rank_initial_results')
@patch('app.build_dataset.graph.node_fetch_full_content')
@patch('app.build_dataset.graph.node_process_full_content')
@patch('app.build_dataset.graph.node_store_results')
async def test_build_data_collection_graph_flow(
    mock_store_results,
    mock_process_full_content,
    mock_fetch_full_content,
    mock_rank_initial_results,
    mock_fetch_initial_results
):
    """Test the basic flow of the LangGraph."""
    mock_fetch_initial_results.return_value = {"initial_search_results": ["result1", "result2"]}
    mock_rank_initial_results.return_value = {"ranked_initial_results": ["ranked1"], "top_n_selected_for_full_fetch": ["ranked1"]}
    mock_fetch_full_content.return_value = {"fetched_full_content": ["full_content1"]}
    mock_process_full_content.return_value = {"processed_structured_data": ["processed1"]}
    mock_store_results.return_value = {"gcs_storage_links": ["link1"]}

    graph = build_data_collection_graph()

    initial_state = GraphState(research_topic="test", current_retry_count=0, error_messages=[])
    final_state = await graph.invoke(initial_state)

    mock_fetch_initial_results.assert_called_once()
    mock_rank_initial_results.assert_called_once()
    mock_fetch_full_content.assert_called_once() # This is an async def, so should be awaited
    mock_process_full_content.assert_called_once()
    mock_store_results.assert_called_once()

    assert final_state.get("gcs_storage_links") == ["link1"]
    mock_rank_initial_results.assert_called_once_with({"research_topic": "test", "current_retry_count": 0, "error_messages": [], "initial_search_results": ["result1", "result2"]})
    # For async functions, use assert_awaited_once_with if the mock itself is an async mock,
    # or if you are checking arguments to an async function that was awaited.
    # Here, node_fetch_full_content is async, so its mock should reflect that if we were testing its internals.
    # However, we are mocking the node function itself, which is called by the graph.
    # The graph invokes it, and the mock_fetch_full_content is what's called.
    # If mock_fetch_full_content was an AsyncMock, then assert_awaited_once_with would be appropriate.
    # Since it's a regular MagicMock here, assert_called_once_with is fine for checking args.
    mock_fetch_full_content.assert_called_once_with({"research_topic": "test", "current_retry_count": 0, "error_messages": [], "initial_search_results": ["result1", "result2"], "ranked_initial_results": ["ranked1"], "top_n_selected_for_full_fetch": ["ranked1"]})
