"""
Tests for the buildDataset feature.
"""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path # Import Path for testing file paths
import math # Import math for checking citation score calculation

# Assume markitdown might not be installed in test env, mock it
# Mock the Markitdown class before it's imported by the module under test
mock_markitdown_instance = MagicMock()
mock_markitdown_instance.convert.return_value = MagicMock(text_content="# Mocked Markdown")
mock_markitdown_class = MagicMock(return_value=mock_markitdown_instance)

# Use patch.dict to temporarily replace the class in the module's namespace
# This needs to happen *before* importing the module that uses Markitdown
# However, patching sys.modules is complex. A simpler way for testing is
# to patch the specific location where it's imported *within* the test function.
# Let's try patching within the test function first.

# If Markitdown is imported at the top level of processors.py, we patch it there.
# If Markitdown is imported *inside* the function, we patch it there.
# Assuming top-level import:
# @patch('app.build_dataset.processors.Markitdown', mock_markitdown_class)

# Import modules *after* potential top-level mocks if needed, but patching in test is safer.
from app.build_dataset.schemas import InitialSearchResult, FullContentData, ProcessedContent
from app.build_dataset.processors import calculate_weighted_quality_score, rank_initial_results, convert_content_to_markdown
from app.build_dataset.tools import search_academic_papers_serpapi, download_pdf_async, fetch_webpage_content
from app.build_dataset.storage import upload_raw_artifact, store_processed_content
from app.build_dataset.graph import build_data_collection_graph, GraphState, node_fetch_initial_results # Import node for direct testing

# --- Tests for Schemas ---

def test_initial_search_result_schema():
    """Test the InitialSearchResult schema including citation_count."""
    data = {
        "link": "https://example.com/paper",
        "title": "Test Paper",
        "snippet": "This is a test snippet.",
        "source_name": "Test Journal",
        "publication_date_str": "2023-01-01",
        "citation_count": 123, # Added
        "raw_serpapi_data": {"some": "data"},
        "quality_score": 0.8
    }
    result = InitialSearchResult(**data)
    assert result.link == "https://example.com/paper"
    assert result.title == "Test Paper"
    assert result.citation_count == 123
    assert result.quality_score == 0.8

def test_full_content_data_schema():
    """Test the FullContentData schema including file_path and optional raw_content."""
    initial_result = InitialSearchResult(link="https://example.com/paper")
    # Test with file_path (PDF case)
    pdf_data = {
        "source_url": "https://example.com/paper.pdf",
        "original_metadata": initial_result,
        "file_path": Path("/tmp/paper.pdf"), # Added
        "raw_content": None, # Changed
        "content_type": "pdf",
        "download_successful": True,
        "error_message": None
    }
    pdf_content_data = FullContentData(**pdf_data)
    assert pdf_content_data.source_url == "https://example.com/paper.pdf"
    assert pdf_content_data.file_path == Path("/tmp/paper.pdf")
    assert pdf_content_data.raw_content is None

    # Test with raw_content (HTML case)
    html_data = {
        "source_url": "https://example.com/page.html",
        "original_metadata": initial_result,
        "file_path": None, # Added
        "raw_content": "<html></html>", # Changed
        "content_type": "html",
        "download_successful": True,
        "error_message": None
    }
    html_content_data = FullContentData(**html_data)
    assert html_content_data.source_url == "https://example.com/page.html"
    assert html_content_data.file_path is None
    assert html_content_data.raw_content == "<html></html>"


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

# Helper function to create InitialSearchResult with specific citation count for testing
def create_test_result(citations: Optional[int], pub_date: str = "2024", title: str = "Test") -> InitialSearchResult:
     # Use MagicMock for original_metadata to avoid needing a real dict with research_topic
     # unless the test specifically needs it (like relevance tests)
    return InitialSearchResult(
        link=f"http://example.com/{title.lower()}",
        title=title,
        snippet="Snippet",
        source_name="arxiv.org", # Assume high authority for simplicity unless testing authority
        publication_date_str=pub_date,
        citation_count=citations,
        original_metadata=MagicMock(research_topic="test topic") # Provide mock metadata
    )

@patch('app.build_dataset.processors.datetime')
def test_calculate_weighted_quality_score_citations(mock_datetime):
    """Test quality score calculation, focusing on citation score."""
    mock_datetime.now.return_value = datetime(2025, 1, 1) # Fix current year

    # Weights used in the function (as of last update)
    weights = {"relevance": 0.4, "recency": 0.2, "source_authority": 0.1, "citations": 0.3}

    res_none = create_test_result(citations=None) # Unknown citations
    res_zero = create_test_result(citations=0)
    res_low = create_test_result(citations=5)
    res_mid = create_test_result(citations=99) # log10(100) / log10(1001) ~ 2/3
    res_high = create_test_result(citations=1000) # log10(1001) / log10(1001) ~ 1.0

    score_none = calculate_weighted_quality_score(res_none)
    score_zero = calculate_weighted_quality_score(res_zero)
    score_low = calculate_weighted_quality_score(res_low)
    score_mid = calculate_weighted_quality_score(res_mid)
    score_high = calculate_weighted_quality_score(res_high)

    # Expected citation scores (approximate, based on log10(count+1)/log10(1001))
    cit_score_none = 0.1 # Default for None
    cit_score_zero = 0.0
    cit_score_low = math.log10(5 + 1) / math.log10(1001) # ~0.26
    cit_score_mid = math.log10(99 + 1) / math.log10(1001) # ~0.66
    cit_score_high = math.log10(1000 + 1) / math.log10(1001) # ~1.0

    # Check relative order
    assert score_high > score_mid
    assert score_mid > score_low
    assert score_low > score_none # Check if low count > unknown default
    assert score_none > score_zero # Check if unknown default > zero

    # Check approximate contribution (isolating citation part)
    # Base score without citations (assuming relevance=0.5, recency=0.9, authority=1.0 for simplicity)
    base_score = (0.5 * weights["relevance"]) + (0.9 * weights["recency"]) + (1.0 * weights["source_authority"]) # ~ 0.2 + 0.18 + 0.1 = 0.48

    assert score_high == pytest.approx(base_score + cit_score_high * weights["citations"])
    assert score_mid == pytest.approx(base_score + cit_score_mid * weights["citations"])
    assert score_low == pytest.approx(base_score + cit_score_low * weights["citations"])
    assert score_none == pytest.approx(base_score + cit_score_none * weights["citations"])
    assert score_zero == pytest.approx(base_score + cit_score_zero * weights["citations"])


@patch('app.build_dataset.processors.datetime')
def test_calculate_weighted_quality_score_recency(mock_datetime):
    """Test quality score calculation, focusing on recency."""
    mock_datetime.now.return_value = datetime(2025, 1, 1)
    recent_result = create_test_result(citations=10, pub_date="2024")
    older_result = create_test_result(citations=10, pub_date="2015")
    very_old_result = create_test_result(citations=10, pub_date="2000")
    score_recent = calculate_weighted_quality_score(recent_result)
    score_older = calculate_weighted_quality_score(older_result)
    score_very_old = calculate_weighted_quality_score(very_old_result)
    assert score_recent > score_older
    assert score_older > score_very_old
    assert score_very_old >= 0

@patch('app.build_dataset.processors.datetime')
def test_calculate_weighted_quality_score_relevance(mock_datetime):
    """Test quality score calculation, focusing on relevance."""
    mock_datetime.now.return_value = datetime(2025, 1, 1)
    topic = "RAG evaluation"
    relevant_result = create_test_result(citations=10, title="RAG Evaluation: New", snippet="Discusses RAG evaluation")
    relevant_result.original_metadata = {"research_topic": topic} # Set topic
    less_relevant_result = create_test_result(citations=10, title="New NLP", snippet="Includes RAG evaluation")
    less_relevant_result.original_metadata = {"research_topic": topic}
    not_relevant_result = create_test_result(citations=10, title="Cats", snippet="Feline behavior")
    not_relevant_result.original_metadata = {"research_topic": topic}
    score_relevant = calculate_weighted_quality_score(relevant_result)
    score_less_relevant = calculate_weighted_quality_score(less_relevant_result)
    score_not_relevant = calculate_weighted_quality_score(not_relevant_result)
    assert score_relevant > score_less_relevant
    assert score_less_relevant > score_not_relevant

@patch('app.build_dataset.processors.datetime')
def test_calculate_weighted_quality_score_source_authority(mock_datetime):
    """Test quality score calculation, focusing on source authority."""
    mock_datetime.now.return_value = datetime(2025, 1, 1)
    high_auth_result = create_test_result(citations=10, title="RAG Eval")
    high_auth_result.source_name = "arxiv.org"
    medium_auth_result = create_test_result(citations=10, title="RAG Eval")
    medium_auth_result.source_name = "ResearchGate"
    low_auth_result = create_test_result(citations=10, title="RAG Eval")
    low_auth_result.source_name = "Personal Blog"
    score_high_auth = calculate_weighted_quality_score(high_auth_result)
    score_medium_auth = calculate_weighted_quality_score(medium_auth_result)
    score_low_auth = calculate_weighted_quality_score(low_auth_result)
    assert score_high_auth > score_medium_auth
    assert score_medium_auth > score_low_auth

@patch('app.build_dataset.processors.calculate_weighted_quality_score')
def test_rank_initial_results(mock_calculate_score):
    """Test the ranking function."""
    mock_calculate_score.side_effect = [0.9, 0.7, 0.5, 0.8, 0.6]
    results = [
        InitialSearchResult(link="http://ex.com/p1", title="Paper 1"),
        InitialSearchResult(link="http://ex.com/p2", title="Paper 2"),
        InitialSearchResult(link="http://ex.com/p3", title="Paper 3"),
        InitialSearchResult(link="http://ex.com/p4", title="Paper 4"),
        InitialSearchResult(link="http://ex.com/p5", title="Paper 5"),
    ]
    top_n = 3
    ranked = rank_initial_results(results, top_n=top_n)
    assert len(ranked) == top_n
    assert ranked[0].quality_score == 0.9
    assert ranked[1].quality_score == 0.8
    assert ranked[2].quality_score == 0.7
    assert rank_initial_results([], top_n=3) == []

# Use patch for the Markitdown class within the processors module
@patch('app.build_dataset.processors.Markitdown')
def test_convert_content_to_markdown_html(mock_markitdown_class):
    """Test processing HTML raw content using mocked Markitdown."""
    # Configure the mock instance returned by the class constructor
    mock_instance = MagicMock()
    mock_instance.convert.return_value = MagicMock(text_content="# Mocked HTML Markdown")
    mock_markitdown_class.return_value = mock_instance

    initial_result = create_test_result(citations=10)
    full_content_html = FullContentData(
        source_url="https://example.com/html",
        original_metadata=initial_result,
        raw_content="<html><body><h1>HTML Content</h1></body></html>",
        content_type="html",
        download_successful=True
    )

    processed = convert_content_to_markdown(full_content_html)

    assert processed is not None
    mock_markitdown_class.assert_called_once_with(enable_plugins=False) # Check instantiation
    mock_instance.convert.assert_called_once_with(full_content_html.raw_content) # Check convert called with HTML string
    assert processed.full_text_markdown == "# Mocked HTML Markdown"

@patch('app.build_dataset.processors.Markitdown')
def test_convert_content_to_markdown_pdf(mock_markitdown_class):
    """Test processing PDF file path using mocked Markitdown."""
    mock_instance = MagicMock()
    mock_instance.convert.return_value = MagicMock(text_content="# Mocked PDF Markdown")
    mock_markitdown_class.return_value = mock_instance

    initial_result = create_test_result(citations=20)
    dummy_pdf_path = Path("/fake/path/doc.pdf")
    full_content_pdf = FullContentData(
        source_url="https://example.com/pdf",
        original_metadata=initial_result,
        file_path=dummy_pdf_path, # Provide file path
        raw_content=None,         # Raw content is None
        content_type="pdf",
        download_successful=True
    )

    processed = convert_content_to_markdown(full_content_pdf)

    assert processed is not None
    mock_markitdown_class.assert_called_once_with(enable_plugins=False) # Check instantiation
    mock_instance.convert.assert_called_once_with(dummy_pdf_path) # Check convert called with Path object
    assert processed.full_text_markdown == "# Mocked PDF Markdown"

@patch('app.build_dataset.processors.Markitdown')
def test_convert_content_to_markdown_no_content(mock_markitdown_class):
    """Test processing when no suitable content is available."""
    initial_result = create_test_result(citations=5)
    full_content_empty = FullContentData(
        source_url="https://example.com/empty",
        original_metadata=initial_result,
        file_path=None,
        raw_content=None, # No content provided
        content_type="unknown",
        download_successful=True
    )
    processed_empty = convert_content_to_markdown(full_content_empty)
    assert processed_empty is None
    mock_markitdown_class.assert_not_called() # Converter shouldn't be called

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
async def test_download_pdf_async(mock_path_class, mock_async_client):
    """Test PDF download tool."""
    # Mock Path object behavior
    mock_output_dir_instance = MagicMock(spec=Path)
    mock_output_path_instance = MagicMock(spec=Path)
    mock_output_path_instance.name = "file.pdf"
    # When Path(url) is called
    mock_path_class.return_value.name = "file.pdf"
    # When output_dir / file_name is called
    mock_output_dir_instance.__truediv__.return_value = mock_output_path_instance

    # Mock httpx response
    mock_response = AsyncMock() # Use AsyncMock for awaitable methods
    mock_response.raise_for_status = AsyncMock(return_value=None)
    mock_response.headers = {"content-type": "application/pdf"}
    mock_response.content = b"fake pdf content"

    # Mock httpx client context manager
    mock_client_instance = AsyncMock()
    mock_client_instance.get = AsyncMock(return_value=mock_response)
    mock_async_client.return_value.__aenter__.return_value = mock_client_instance

    # Mock open context manager
    mock_open = MagicMock()
    mock_file_handle = MagicMock()
    mock_open.return_value.__enter__.return_value = mock_file_handle

    with patch('builtins.open', mock_open):
        downloaded_path = await download_pdf_async("http://example.com/file.pdf", mock_output_dir_instance)

    mock_output_dir_instance.mkdir.assert_called_once_with(parents=True, exist_ok=True)
    mock_client_instance.get.assert_awaited_once_with("http://example.com/file.pdf")
    mock_open.assert_called_once_with(mock_output_path_instance, "wb")
    mock_file_handle.write.assert_called_once_with(b"fake pdf content")
    assert downloaded_path == mock_output_path_instance


@patch('app.build_dataset.tools.httpx.AsyncClient')
@patch('app.build_dataset.tools.settings')
async def test_fetch_webpage_content(mock_settings, mock_async_client):
    """Test Playwright MCP tool wrapper."""
    mock_settings.PLAYWRIGHT_MCP_URL = "http://fake-mcp:8070/extract"

    mock_response = AsyncMock()
    mock_response.raise_for_status = AsyncMock(return_value=None)
    mock_response.json = MagicMock(return_value={"status": "success", "content": "fake webpage content"}) # json() is sync

    mock_client_instance = AsyncMock()
    mock_client_instance.post = AsyncMock(return_value=mock_response)
    mock_async_client.return_value.__aenter__.return_value = mock_client_instance

    content = await fetch_webpage_content("http://example.com/page")

    mock_client_instance.post.assert_awaited_once_with(
        "http://fake-mcp:8070/extract",
        json={"url": "http://example.com/page"}
    )
    assert content == "fake webpage content"

# --- Tests for Storage (Basic mocking) ---

@patch('app.build_dataset.storage.storage.Client')
@patch('app.build_dataset.storage.settings')
@patch('app.build_dataset.storage.Path')
def test_upload_raw_artifact(mock_path_class, mock_settings, mock_storage_client):
    """Test GCS upload function."""
    mock_settings.GCS_BUCKET_NAME = "fake-bucket"
    mock_settings.GCS_PROJECT = None
    mock_settings.GCS_SERVICE_ACCOUNT_FILE = None

    # Mock Path().exists()
    mock_path_instance = MagicMock()
    mock_path_instance.exists.return_value = False # Assume service account file doesn't exist
    mock_path_class.return_value = mock_path_instance

    mock_client_instance = MagicMock()
    mock_storage_client.return_value = mock_client_instance

    mock_bucket_instance = MagicMock()
    mock_client_instance.bucket.return_value = mock_bucket_instance

    mock_blob_instance = MagicMock()
    mock_bucket_instance.blob.return_value = mock_blob_instance

    mock_source_file_path = MagicMock(spec=Path) # Mock the source file path

    uploaded_url = upload_raw_artifact(
        "fake-bucket",
        mock_source_file_path,
        "fake/destination/blob.md"
    )

    mock_storage_client.assert_called_once_with() # Called with default ADC
    mock_client_instance.bucket.assert_called_once_with("fake-bucket")
    mock_bucket_instance.blob.assert_called_once_with("fake/destination/blob.md")
    mock_blob_instance.upload_from_filename.assert_called_once_with(mock_source_file_path)
    assert uploaded_url == "https://storage.googleapis.com/fake-bucket/fake/destination/blob.md"

@patch('app.build_dataset.storage.upload_raw_artifact')
@patch('app.build_dataset.storage.Path')
@patch('builtins.open')
def test_store_processed_content(mock_open, mock_path_class, mock_upload_raw_artifact_func):
    """Test storing processed content."""
    # Mock Path object behavior for temp dir
    mock_temp_dir_instance = MagicMock(spec=Path)
    mock_temp_file_instance = MagicMock(spec=Path)
    mock_path_class.return_value = mock_temp_dir_instance
    mock_temp_dir_instance.mkdir.return_value = None
    mock_temp_dir_instance.iterdir.return_value = [mock_temp_file_instance] # Simulate one temp file
    mock_temp_dir_instance.__truediv__.return_value = mock_temp_file_instance # Path() / "filename"

    # Mock open context manager
    mock_file_handle = MagicMock()
    mock_open.return_value.__enter__.return_value = mock_file_handle

    # Simulate successful upload for the first item, failed for the second
    mock_upload_raw_artifact_func.side_effect = ["http://gcs.link/file1.md", None]

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

    # Check cleanup was attempted
    mock_temp_dir_instance.iterdir.assert_called()
    mock_temp_file_instance.unlink.assert_called_once() # Check unlink on the temp file mock
    mock_temp_dir_instance.rmdir.assert_called_once()

    assert store_processed_content([]) == []

# --- Tests for Graph Nodes ---

@patch('app.build_dataset.graph.search_academic_papers_serpapi')
def test_node_fetch_initial_results_citation_parsing(mock_search_api):
    """Test citation parsing within the fetch node."""
    # Mock SerpAPI response with various citation formats
    mock_search_api.return_value = [
        {"link": "http://ex.com/1", "title": "High Citations", "cited_by": {"value": 1234}},
        {"link": "http://ex.com/2", "title": "Zero Citations", "cited_by": {"value": 0}},
        {"link": "http://ex.com/3", "title": "String Citations", "cited_by": {"value": "56"}},
        {"link": "http://ex.com/4", "title": "Missing Value", "cited_by": {}},
        {"link": "http://ex.com/5", "title": "Missing Cited By"},
        {"link": "http://ex.com/6", "title": "Invalid Value", "cited_by": {"value": "abc"}},
        {"link": "http://ex.com/7", "title": "None Value", "cited_by": {"value": None}},
    ]
    initial_state = GraphState(research_topic="test", error_messages=[])
    result_state = node_fetch_initial_results(initial_state)

    results = result_state["initial_search_results"]
    assert len(results) == 7
    assert results[0].citation_count == 1234
    assert results[1].citation_count == 0
    assert results[2].citation_count == 56
    assert results[3].citation_count is None
    assert results[4].citation_count is None
    assert results[5].citation_count is None # Invalid value treated as None
    assert results[6].citation_count is None # None value treated as None

# --- Basic Graph Test (Requires minimal setup) ---

@patch('app.build_dataset.graph.node_fetch_initial_results', new_callable=AsyncMock)
@patch('app.build_dataset.graph.node_rank_initial_results', new_callable=AsyncMock)
@patch('app.build_dataset.graph.node_fetch_full_content', new_callable=AsyncMock)
@patch('app.build_dataset.graph.node_process_full_content', new_callable=AsyncMock)
@patch('app.build_dataset.graph.node_store_results', new_callable=AsyncMock)
async def test_build_data_collection_graph_flow(
    mock_store_results,
    mock_process_full_content,
    mock_fetch_full_content,
    mock_rank_initial_results,
    mock_fetch_initial_results # Mocks are now AsyncMocks where appropriate
):
    """Test the basic flow of the LangGraph."""
    # Mock node return values to simulate state transitions
    # Ensure mocks return dicts compatible with GraphState updates
    mock_fetch_initial_results.return_value = {"initial_search_results": ["result1", "result2"], "error_messages": []}
    mock_rank_initial_results.return_value = {"ranked_initial_results": ["ranked1"], "top_n_selected_for_full_fetch": ["ranked1"], "error_messages": []}
    mock_fetch_full_content.return_value = {"fetched_full_content": ["full_content1"], "error_messages": []}
    mock_process_full_content.return_value = {"processed_structured_data": ["processed1"], "error_messages": []}
    mock_store_results.return_value = {"gcs_storage_links": ["link1"], "error_messages": []}

    graph = build_data_collection_graph()

    # Run the graph with a dummy initial state
    initial_state = GraphState(research_topic="test", current_retry_count=0, error_messages=[])
    final_state = await graph.ainvoke(initial_state) # Use ainvoke for async graph

    # Assert that each node was called once
    mock_fetch_initial_results.assert_awaited_once()
    mock_rank_initial_results.assert_awaited_once()
    mock_fetch_full_content.assert_awaited_once()
    mock_process_full_content.assert_awaited_once()
    mock_store_results.assert_awaited_once()

    # Assert the final state contains the expected data from the last node
    assert final_state.get("gcs_storage_links") == ["link1"]
    # Assert intermediate states were passed correctly (checking inputs to mocked nodes)
    # Note: AsyncMock uses await_args or await_args_list
    mock_rank_initial_results.assert_awaited_once_with(initial_state | mock_fetch_initial_results.return_value)
    mock_fetch_full_content.assert_awaited_once_with(initial_state | mock_fetch_initial_results.return_value | mock_rank_initial_results.return_value)
