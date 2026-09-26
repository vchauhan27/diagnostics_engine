import datetime
import decimal
import uuid
from typing import Any

from langchain_core.tools import tool
from langgraph.config import get_stream_writer

from .config import code_changes_db, embeddings
from AIAgent.db import get_pool, init_pool
from AIAgent.parser import FailureParser

# -----------------------------------------------------------------------
# Serialisation helper
# -----------------------------------------------------------------------

def _json_safe(obj: Any) -> Any:
    """Recursively convert non-JSON-serializable types returned by psycopg2
    (datetime, date, Decimal, UUID, memoryview) into JSON-safe primitives.
    Applied to every row dict before it leaves a tool so that LangGraph's
    streaming serialiser never encounters a raw datetime.
    """
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    if isinstance(obj, datetime.date):
        return obj.isoformat()
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, memoryview):
        return bytes(obj).decode("utf-8", errors="replace")
    return obj


# -----------------------------------------------------------------------
# Tool 1 — Test Case Details  (real PostgreSQL: test_cases + projects)
# -----------------------------------------------------------------------

@tool
async def get_test_details(test_case_id: str) -> dict:
    """
    Retrieve structured details for a test case from PostgreSQL.
    Looks up by test_case_id (UUID) or test_name (string identifier).
    """
    try:
        writer = get_stream_writer()
    except RuntimeError:
        writer = None
    if writer: writer({"status": f"Fetching test details for {test_case_id}..."})

    query = """
        SELECT
            tc.test_case_id,
            tc.project_id,
            p.project_name,
            tc.feature_id,
            tc.title,
            tc.test_name,
            tc.description,
            tc.preconditions,
            tc.test_steps,
            tc.expected_result,
            tc.priority,
            tc.severity,
            tc.status,
            tc.version,
            tc.source,
            tc.created_at,
            tc.updated_at
        FROM test_cases AS tc
        JOIN projects AS p
            ON tc.project_id = p.project_id
        WHERE tc.test_case_id::text = %s OR tc.test_name = %s;
    """

    pool = get_pool()

    await init_pool()
    async with pool.connection() as conn, conn.cursor() as cursor:
        await cursor.execute("SET statement_timeout = 10000")

        await cursor.execute(query, (test_case_id, test_case_id))
        row = await cursor.fetchone()

        if row is None:
            return {
                "found": False,
                "test_case_id": test_case_id,
                "message": "Test case not found."
            }

        columns = [description[0] for description in (cursor.description or [])]
        result = _json_safe(dict(zip(columns, row)))

    db_result = {"found": True, "test_case": result}
    return db_result


# -----------------------------------------------------------------------
# Tool 2 — Related Defects  (real PostgreSQL: defects table — Jira data)
# -----------------------------------------------------------------------

@tool
async def search_related_defects(
    module: str,
    severity: str | None = None,
    status_filter: str | None = None,
    environment: str | None = None,
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """
    Query the real defects table (Jira-style issues) for defects in the same
    module as the failing test, optionally filtered by severity, status, and
    environment.

    Use this tool to find OPEN or IN_PROGRESS defects that match the component
    of the current failure — these are strong signals that the failure is a
    known issue already tracked in the system.

    Also surfaces RESOLVED defects so the agent can detect regressions (a bug
    marked FIXED that has re-appeared).

    Args:
        module:        The feature module to search (e.g. 'Payment', 'Authentication').
        severity:      Optional. Filter to CRITICAL, MAJOR, MINOR, or LOW.
        status_filter: Optional. Filter to OPEN, IN_PROGRESS, RESOLVED, or CLOSED.
                       Leave None to return all statuses.
        environment:   Optional. Filter by environment (production, staging, qa, dev).
        top_k:         Maximum number of defects to return (default 10, max 50).
    """
    try:
        writer = get_stream_writer()
    except RuntimeError:
        writer = None
    if writer: writer({"status": f"Searching related defects for module {module}..."})

    top_k = min(top_k, 50)

    # Build dynamic WHERE clause
    conditions = ["LOWER(module) = LOWER(%s)"]
    params: list[Any] = [module]

    if severity:
        conditions.append("severity = %s")
        params.append(severity.upper())

    if status_filter:
        conditions.append("status = %s")
        params.append(status_filter.upper())

    if environment:
        conditions.append("LOWER(environment) = LOWER(%s)")
        params.append(environment)

    where_clause = " AND ".join(conditions)
    params.append(top_k)

    query = f"""
        SELECT
            d.defect_id,
            d.issue_key,
            d.issue_type,
            d.title,
            d.description,
            d.module,
            d.severity,
            d.status,
            d.resolution,
            d.labels,
            d.affects_versions,
            d.fix_versions,
            d.environment,
            d.reported_at,
            d.updated_at,
            d.resolved_at,
            d.assignee_id IS NOT NULL AS is_assigned,
            p.project_name
        FROM defects AS d
        JOIN projects AS p ON d.project_id = p.project_id
        WHERE {where_clause}
        ORDER BY
            CASE d.severity
                WHEN 'CRITICAL' THEN 1
                WHEN 'MAJOR'    THEN 2
                WHEN 'MINOR'    THEN 3
                WHEN 'LOW'      THEN 4
                ELSE 5
            END,
            CASE d.status
                WHEN 'OPEN'        THEN 1
                WHEN 'IN_PROGRESS' THEN 2
                WHEN 'RESOLVED'    THEN 3
                WHEN 'CLOSED'      THEN 4
                ELSE 5
            END,
            d.reported_at DESC
        LIMIT %s;
    """

    pool = get_pool()

    results = []
    await init_pool()
    async with pool.connection() as conn, conn.cursor() as cursor:
        await cursor.execute("SET statement_timeout = 10000")
        await cursor.execute(query, params)
        rows = await cursor.fetchall()
        columns = [d[0] for d in (cursor.description or [])]
        for row in rows:
            results.append(_json_safe(dict(zip(columns, row))))

    return results


# -----------------------------------------------------------------------
# Tool 3 — Execution History  (real PostgreSQL: test_executions table)
# -----------------------------------------------------------------------

@tool
async def get_execution_history(
    test_case_id: str,
    last_n: int = 10,
) -> dict:
    """
    Retrieve the recent execution history for a specific test case from the
    real test_executions table.

    Use this tool to understand the failure pattern:
    - Is this test consistently failing (systematic issue)?
    - Did it recently start failing after a period of passing (regression)?
    - Is it flaky (intermittent PASS/FAIL/BLOCKED)?

    Args:
        test_case_id: UUID or test_name of the test case.
        last_n:       How many recent executions to return (default 10, max 50).
    """
    try:
        writer = get_stream_writer()
    except RuntimeError:
        writer = None
    if writer: writer({"status": f"Fetching execution history for test case {test_case_id}..."})

    last_n = min(last_n, 50)

    query = """
        SELECT
            te.execution_id,
            te.status,
            te.build_id,
            te.device,
            te.environment,
            te.notes,
            te.executed_at
        FROM test_executions AS te
        WHERE te.test_case_id::text = %s
        ORDER BY te.executed_at DESC
        LIMIT %s;
    """

    pool = get_pool()

    rows_out = []
    await init_pool()
    async with pool.connection() as conn, conn.cursor() as cursor:
        await cursor.execute("SET statement_timeout = 10000")
        await cursor.execute(query, (test_case_id, last_n))
        rows = await cursor.fetchall()
        columns = [d[0] for d in (cursor.description or [])]
        for row in rows:
            rows_out.append(_json_safe(dict(zip(columns, row))))

    if not rows_out:
        result = {
            "found": False,
            "test_case_id": test_case_id,
            "message": "No execution history found for this test case.",
            "executions": [],
            "summary": {},
        }
        return result

    # Build a quick summary the LLM can read at a glance
    statuses = [r["status"] for r in rows_out]
    passed   = statuses.count("PASSED")
    failed   = statuses.count("FAILED")
    blocked  = statuses.count("BLOCKED")
    total    = len(statuses)

    # Failure pattern detection
    last_3 = statuses[:3]
    if all(s == "FAILED" for s in last_3):
        pattern = "consistently_failing"
    elif statuses[0] == "FAILED" and "PASSED" in statuses[1:4]:
        pattern = "regression"  # was passing, now failing
    elif statuses.count("FAILED") / total > 0.3 and statuses.count("PASSED") / total > 0.3:
        pattern = "flaky"
    else:
        pattern = "stable"

    result = {
        "found": True,
        "test_case_id": test_case_id,
        "executions": rows_out,
        "summary": {
            "total":    total,
            "passed":   passed,
            "failed":   failed,
            "blocked":  blocked,
            "pass_rate": round(passed / total * 100, 1) if total else 0,
            "pattern":  pattern,
            "latest_status":      statuses[0] if statuses else None,
            "latest_build":       rows_out[0].get("build_id") if rows_out else None,
            "latest_environment": rows_out[0].get("environment") if rows_out else None,
        },
    }

    return result


# -----------------------------------------------------------------------
# -----------------------------------------------------------------------
# Tool 4 — Historical Failures  (PostgreSQL pgvector search)
# -----------------------------------------------------------------------

@tool
async def search_historical_failures(
    error_type: str,
    product_name: str,
    error_message: str,
    component: str,
    environment: str | None = None,
    historical_top_k: int = 5,
) -> list[dict[str, Any]]:
    """
    Find historical failures that are semantically similar to the current failure
    using vector search over PostgreSQL pgvector columns.
    """
    try:
        writer = get_stream_writer()
    except RuntimeError:
        writer = None
    if writer: writer({"status": f"Searching historical failures related to {component}..."})

    search_text = f"""
    Error type: {error_type}
    Error message: {error_message}
    Component: {component}
    environment: {environment or "Unknown"}
    """

    # Generate embedding for the search query
    query_vector = await embeddings.aembed_query(search_text)
    
    # We query both defects and test_executions tables and combine the results.
    # We format the vector as a string array for psycopg to pass to pgvector.
    vector_str = "[" + ",".join(map(str, query_vector)) + "]"
    
    # We query BOTH tables. Note: Since we are looking for the top K overall,
    # we can use a UNION ALL and then ORDER BY the distance.
    # To use the index efficiently, we order and limit each table, then union and order again.
    
    query = """
    WITH combined_results AS (
        (
            SELECT
                defect_id as id,
                'defect' as source_type,
                title,
                description as content,
                module as component,
                status,
                environment,
                embedding <=> %s::vector as distance
            FROM defects
            WHERE embedding IS NOT NULL
            ORDER BY distance LIMIT %s
        )

        UNION ALL

        (
            SELECT
                te.execution_id::text as id,
                'test_execution' as source_type,
                tc.title,
                tc.description || ' Notes: ' || COALESCE(te.notes, '') as content,
                'test_case' as component,
                te.status,
                te.environment,
                te.embedding <=> %s::vector as distance
            FROM test_executions te
            JOIN test_cases tc ON te.test_case_id = tc.test_case_id
            WHERE te.embedding IS NOT NULL
            ORDER BY distance LIMIT %s
        )
    )
    SELECT * FROM combined_results
    ORDER BY distance
    LIMIT %s;
    """
    
    pool = get_pool()
    
    results = []
    await init_pool()
    async with pool.connection() as conn, conn.cursor() as cursor:
            try:
                await cursor.execute(query, (vector_str, historical_top_k, vector_str, historical_top_k, historical_top_k))
                rows = await cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                for row in rows:
                    data = dict(zip(columns, row))
                    # Format into a document-like structure for the agent
                    content = f"Title: {data['title']}\n"
                    content += f"Type: {data['source_type']}\n"
                    content += f"Component: {data['component']}\n"
                    content += f"Status: {data['status']}\n"
                    content += f"Environment: {data['environment']}\n"
                    content += f"Content: {data['content']}\n"
                    
                    results.append({
                        "content": content,
                        "metadata": {
                            "source": f"{data['source_type']}_{data['id']}",
                            "distance": float(data['distance'])
                        }
                    })
            except Exception as e:  # noqa: BLE001
                print(f"Vector search failed: {e}")

    return results

# -----------------------------------------------------------------------

@tool
async def search_code_changes(
    error_message: str,
    component: str,
    product_name: str,
    environment: str | None = None,
    code_changes_top_k: int = 5,
) -> list[dict[str, Any]]:
    """
    Find code changes that may be related to the current test failure using
    vector search over the pgvector code-changes index.
    """
    try:
        writer = get_stream_writer()
    except RuntimeError:
        writer = None
    if writer: writer({"status": f"Searching code changes related to {component}..."})

    search_text = f"""
    Component: {component}
    environment: {environment or "Unknown"}
    Error message: {error_message or "Unknown"}
    """

    raw_results = await code_changes_db.asimilarity_search(
        search_text,
        k=code_changes_top_k,
        filter={"product": product_name}
    )

    results: list[dict[str, Any]] = [
        {"content": document.page_content, "metadata": document.metadata}
        for document in raw_results
    ]

    return results

@tool
def parse_failure_log(log_text: str) -> dict:
    """
    Parse a raw failure log text into a structured FailureInput containing test_case_id, error_message, stack_trace, and component.
    Use this when the user pastes a raw failure log in the chat.
    """
    try:
        writer = get_stream_writer()
    except RuntimeError:
        writer = None
    if writer: writer({"status": "Parsing failure log text..."})
    
    parser = FailureParser()
    parsed = parser.parse_text(log_text)
    return parsed.to_failure_input_dict()

@tool
def get_assigned_test_cases(user_id: str = "current_user") -> list[str]:
    """
    Get the list of test cases (by test_case_id or test_name) that are currently assigned to the user.
    Use this to verify if you are allowed to answer queries about a specific test case.
    """
    try:
        writer = get_stream_writer()
    except RuntimeError:
        writer = None
    if writer: writer({"status": f"Fetching assigned test cases for {user_id}..."})
    
    # Mocking assigned test cases for demonstration
    # In a real scenario, this would query a user_assignments table.
    return ["TC-1234", "TC-5678", "auth_login_test", "payment_processing_test", "UNKNOWN"]

@tool
def ask_user_jira_approval(question: str) -> str:
    """
    Use this tool when you are confused or unsure about the diagnosis and want to ask the user whether to approve, reject, or make changes to the Jira ticket.
    The user's response will be returned as a string.
    """
    return "" # Implementation is skipped by HumanInTheLoopMiddleware

