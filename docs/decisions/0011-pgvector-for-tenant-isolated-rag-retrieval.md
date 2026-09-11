# ADR 0011: PostgreSQL pgvector for Tenant-Isolated Vector Retrieval

- **Status**: Approved
- **Date**: 2026-09-11
- **Deciders**: Lead Engineering Agent, Project Owner

---

## 1. Context & Problem Statement

Car-Export-CRM requires retrieval of approved company knowledge (FAQs, European vehicle export procedures, customs rules, pricing terms) to assist sales reps with grounded response suggestions.

We must select the vector storage and retrieval architecture. The design must guarantee strict multi-tenant isolation (`INV-001`, `BR-002`), minimize infrastructure complexity for the MVP, and support fast cosine similarity search across tenant-scoped document chunks.

---

## 2. Decision Drivers

- **Strict Tenant Isolation**: Vector searches MUST be scoped by `tenant_id` at the database index layer. Cross-tenant knowledge retrieval is a critical security vulnerability.
- **Operational Simplicity**: Avoid managing separate vector database clusters (Pinecone, Qdrant, Milvus) for MVP.
- **ACID Transaction Alignment**: Document metadata updates, embedding storage, and audit logs should reside in a single transactional database engine.

---

## 3. Considered Options

1. **Option 1**: Dedicated Managed Vector Database (Pinecone, Qdrant, Weaviate).
2. **Option 2**: PostgreSQL + `pgvector` extension within the primary relational database.
3. **Option 3**: In-Memory Python Vector Indexing (FAISS / ChromaDB local file).

---

## 4. Decision Outcome

**Chosen Option**: **Option 2: PostgreSQL + `pgvector` extension**.

### Specifications:

1. **Schema & Extension**:
   - Enable `CREATE EXTENSION IF NOT EXISTS vector;` in PostgreSQL.
   - Embeddings stored in `knowledge_embeddings` table:
     `embedding vector(1536)` (for 1536-dimensional text-embedding-3-small vectors) or standard 768/1536 dimensions.
   - Column mapping: `id UUID`, `tenant_id UUID NOT NULL REFERENCES tenants(id)`, `document_id UUID REFERENCES documents(id)`, `chunk_text TEXT`, `embedding vector(1536)`.

2. **Tenant-Isolated Vector Search Query**:
   ```sql
   SELECT chunk_text, document_id, 1 - (embedding <=> :query_embedding) AS similarity
   FROM knowledge_embeddings
   WHERE tenant_id = :current_tenant_id
   ORDER BY embedding <=> :query_embedding ASC
   LIMIT :top_k;
   ```

3. **Index Strategy**: HNSW (Hierarchical Navigable Small World) index or IVFFlat index scoped by `tenant_id`.

---

## 5. Consequences

### Positive:
- Zero additional database infrastructure to deploy or monitor for MVP.
- Strict database-enforced multi-tenant row isolation using the existing `tenant_id` security model.
- Atomic ACID transactions for document creation, chunking, and embedding storage.

### Negative / Mitigation:
- Requires installing `pgvector` extension on PostgreSQL instance. (Standard in AWS RDS, GCP Cloud SQL, and official Docker PostgreSQL images).
