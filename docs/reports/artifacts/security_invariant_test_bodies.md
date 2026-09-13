# Security Invariant Executable Test Bodies (`SEC-001` – `SEC-011`)

This document provides the full Python executable source code, test function definitions, fixtures, and assertion statements verifying all 11 security invariants for the Car-Export-CRM platform.

---

## `SEC-001`: Server-Side Identity Context Extraction
- **File**: [`src/backend/tests/api/test_auth_middleware.py`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/src/backend/tests/api/test_auth_middleware.py)

```python
@pytest.mark.asyncio
async def test_auth_middleware_extracts_user_and_tenant_context(client: AsyncClient) -> None:
    """Verify auth middleware parses valid JWT tokens and populates request.state context."""
    user_id = str(uuid7())
    tenant_id = str(uuid7())
    token = create_access_token(data={"sub": user_id, "tenant_id": tenant_id, "role": "sales_rep"})

    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user_id
    assert data["tenant_id"] == tenant_id
    assert data["role"] == "sales_rep"
```

---

## `SEC-002`: Client `tenant_id` Body Override Rejection
- **File**: [`src/backend/tests/api/test_tenant_context.py`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/src/backend/tests/api/test_tenant_context.py)

```python
@pytest.mark.asyncio
async def test_tenant_context_rejects_client_body_tenant_id_override(
    client: AsyncClient, auth_headers_tenant_a: dict
) -> None:
    """Verify API endpoints reject client attempts to specify or override tenant_id in request bodies."""
    malicious_payload = {
        "first_name": "Target",
        "last_name": "Customer",
        "phone": "+21698765432",
        "tenant_id": str(uuid7()),  # Malicious tenant ID override attempt
    }

    response = await client.post("/api/v1/customers", json=malicious_payload, headers=auth_headers_tenant_a)

    # Must reject with HTTP 422 Unprocessable Entity or strip payload tenant_id in favor of auth token tenant_id
    if response.status_code == 201:
        created_customer = response.json()
        assert created_customer["tenant_id"] != malicious_payload["tenant_id"]
        assert created_customer["tenant_id"] == TENANT_A_ID
    else:
        assert response.status_code == 422
```

---

## `SEC-003`: Mandatory `.where(tenant_id)` Repository Filter
- **File**: [`src/backend/tests/security/test_idor_isolation.py`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/src/backend/tests/security/test_idor_isolation.py)

```python
@pytest.mark.asyncio
async def test_repository_base_applies_mandatory_tenant_id_filter(db_session: AsyncSession) -> None:
    """Verify repository queries automatically inject .where(Model.tenant_id == tenant_id)."""
    repo = CustomerRepository(db_session=db_session, tenant_id=TENANT_A_ID)
    stmt = repo._build_base_query()

    compiled_sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "customers.tenant_id =" in compiled_sql
    assert str(TENANT_A_ID) in compiled_sql
```

---

## `SEC-004`: ARQ Task Queue Tenant Context Scoping
- **File**: [`src/backend/tests/security/test_audit_logging.py`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/src/backend/tests/security/test_audit_logging.py)

```python
@pytest.mark.asyncio
async def test_arq_job_context_retains_tenant_isolation(mock_arq_redis: AsyncMock) -> None:
    """Verify ARQ background worker jobs propagate and retain initiating tenant_id context."""
    job_payload = {
        "task_name": "send_whatsapp_message",
        "tenant_id": TENANT_A_ID,
        "message_id": str(uuid7()),
    }

    ctx = {"redis": mock_arq_redis, "tenant_id": job_payload["tenant_id"]}
    result = await process_background_job(ctx, job_payload)

    assert result["success"] is True
    assert result["executed_tenant_id"] == TENANT_A_ID
```

---

## `SEC-005`: Redis Cache Key Tenant Prefixing (`tenant:{id}:...`)
- **File**: [`src/backend/tests/api/test_correlation.py`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/src/backend/tests/api/test_correlation.py)

```python
@pytest.mark.asyncio
async def test_redis_cache_keys_include_tenant_prefix() -> None:
    """Verify all Redis cache keys enforce tenant namespace prefixing to prevent cache pollution."""
    cache_service = TenantCacheService(tenant_id=TENANT_A_ID)
    cache_key = cache_service.build_key("vehicle_catalog", "page_1")

    assert cache_key == f"tenant:{TENANT_A_ID}:vehicle_catalog:page_1"
    assert "tenant:" in cache_key
```

---

## `SEC-006`: Private S3 Pre-Signed URLs (15-Min TTL)
- **File**: [`src/backend/tests/security/test_idor_isolation.py`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/src/backend/tests/security/test_idor_isolation.py)

```python
@pytest.mark.asyncio
async def test_s3_storage_generates_15min_presigned_urls(mock_s3_client: AsyncMock) -> None:
    """Verify document storage generates pre-signed GET URLs with maximum 15-minute expiration."""
    storage_service = ObjectStorageService(s3_client=mock_s3_client)
    url = await storage_service.generate_presigned_url(
        bucket="car-crm-docs", object_key=f"{TENANT_A_ID}/pdf/quote_001.pdf", expires_in=900
    )

    assert "X-Amz-Expires=900" in url or mock_s3_client.generate_presigned_url.call_args[1]["ExpiresIn"] <= 900
```

---

## `SEC-007`: Vector RAG Search `WHERE tenant_id` Scoping
- **File**: [`src/backend/tests/security/test_idor_isolation.py`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/src/backend/tests/security/test_idor_isolation.py)

```python
@pytest.mark.asyncio
async def test_vector_rag_search_scopes_by_tenant_id(db_session: AsyncSession) -> None:
    """Verify pgvector similarity search injects mandatory WHERE tenant_id filter."""
    vector_service = VectorStoreService(db_session=db_session, tenant_id=TENANT_A_ID)
    query_vector = [0.1] * 1536

    results = await vector_service.similarity_search(query_vector=query_vector, top_k=5)

    for item in results:
        assert item.tenant_id == TENANT_A_ID
```

---

## `SEC-008`: Cross-Tenant Data Exclusion in AI Prompts
- **File**: [`src/backend/tests/ai/test_prompt_injection.py`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/src/backend/tests/ai/test_prompt_injection.py)

```python
@pytest.mark.asyncio
async def test_ai_prompt_builder_excludes_cross_tenant_context() -> None:
    """Verify AI prompt construction strictly filters out context from other tenants."""
    builder = PromptContextBuilder(tenant_id=TENANT_A_ID)
    prompt_text = builder.build_extraction_prompt(
        message_history=[
            {"tenant_id": TENANT_A_ID, "content": "I want a BMW X5 under FCR regime"},
            {"tenant_id": TENANT_B_ID, "content": "SECRET_DATA_TENANT_B"},
        ]
    )

    assert "BMW X5" in prompt_text
    assert "SECRET_DATA_TENANT_B" not in prompt_text
```

---

## `SEC-009`: Structured JSON Log Scrubbing & Audit Ledger
- **File**: [`src/backend/tests/security/test_log_scrubbing.py`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/src/backend/tests/security/test_log_scrubbing.py)

```python
def test_json_logger_scrubs_sensitive_credentials_and_tokens(caplog: pytest.LogCaptureFixture) -> None:
    """Verify logger scrubs authorization headers, passwords, and sensitive fields."""
    logger = get_structured_logger("test_scrubber")
    logger.info("User login attempt", extra={"authorization": "Bearer secret_token_123", "password": "my_password"})

    log_json = caplog.text
    assert "secret_token_123" not in log_json
    assert "my_password" not in log_json
    assert "Bearer ***" in log_json
```

---

## `SEC-010`: Cross-Tenant Access Returns HTTP 404 (`AC-01`)
- **File**: [`src/backend/tests/api/test_idor_defense.py`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/src/backend/tests/api/test_idor_defense.py)

```python
@pytest.mark.asyncio
async def test_cross_tenant_access_returns_404_not_found(
    client: AsyncClient, auth_headers_tenant_a: dict, customer_tenant_b_id: str
) -> None:
    """Verify accessing another tenant's resource returns HTTP 404 (Masking Existence) instead of 403."""
    response = await client.get(f"/api/v1/customers/{customer_tenant_b_id}", headers=auth_headers_tenant_a)

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "RESOURCE_NOT_FOUND"
```

---

## `SEC-011`: Async Worker Poison Payload Retry & DLQ
- **File**: [`src/backend/tests/security/test_audit_logging.py`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/src/backend/tests/security/test_audit_logging.py)

```python
@pytest.mark.asyncio
async def test_async_worker_poison_payload_routes_to_dlq(db_session: AsyncSession) -> None:
    """Verify poison worker payload retries 3 times then moves to Dead-Letter Queue (DLQ)."""
    poison_payload = {"malformed_json": True, "tenant_id": TENANT_A_ID}
    worker = ARQWorkerHandler(db_session=db_session)

    with pytest.raises(ValueError):
        await worker.execute_job_with_retry(poison_payload, max_retries=3)

    dlq_entry = await db_session.execute(
        select(DLQEvent).where(DLQEvent.tenant_id == TENANT_A_ID)
    )
    event = dlq_entry.scalar_one()
    assert event.retry_count == 3
    assert event.status == "DEAD_LETTERED"
```
