# ADR 0005: PostgreSQL as Primary Database & UUIDv7 Identifier Strategy

- **Status**: Approved
- **Date**: 2026-09-11
- **Deciders**: Lead Engineering Agent, Project Owner

---

## 1. Context & Problem Statement

Car-Export-CRM requires a reliable relational database engine and primary key identifier strategy. 

The system handles structured business entities (Tenants, Customers, Leads, Vehicles, Quotes), rich semi-structured data (WhatsApp webhook payloads, AI extractions), and audit logs. Primary keys must support multi-tenant security (preventing enumeration attacks), distributed ID generation across API servers and background workers, and optimal B-Tree index performance in PostgreSQL.

---

## 2. Decision Drivers

- **Relational Integrity & Financial Precision**: Foreign keys, ACID transactions, and exact decimal types for multi-currency export math.
- **Enumeration Attack Prevention**: Sequential integer IDs (`1, 2, 3...`) expose business volume and permit IDOR guessing attacks across tenant endpoints.
- **Indexing & Insertion Performance**: Standard random UUIDv4 causes severe B-Tree index page splitting and cache miss degradation at scale.
- **Distributed Generation**: Ability to generate globally unique IDs in application layers without round-tripping to database sequences.

---

## 3. Considered Options

### Primary Database:
1. **Option 1**: PostgreSQL (Primary Relational Engine with JSONB).
2. **Option 2**: MySQL / MariaDB.
3. **Option 3**: MongoDB / NoSQL document store.

### Identifier Strategy:
1. **Option A**: Auto-incrementing `BIGINT` / Sequences.
2. **Option B**: Random `UUIDv4`.
3. **Option C**: Time-ordered `UUIDv7` (RFC 9562).

---

## 4. Decision Outcome

**Chosen Option**: **PostgreSQL** paired with **UUIDv7 Primary Keys**.

### Rationale:
- **PostgreSQL**: Industry standard for transactional reliability, supporting robust JSONB document indexing, full-text search (`pg_trgm`, `tsvector`), and multi-tenant security control.
- **UUIDv7**: Combines a 48-bit UNIX millisecond timestamp with 74 bits of cryptographically strong pseudo-randomness.
  - **Sequential B-Tree Locality**: Monotonically increasing timestamps cluster new inserts on the right side of B-Tree index pages, eliminating random I/O and index fragmentation.
  - **Enumeration Protection**: 74 random bits make ID guessing computationally impossible.
  - **No Database Lock / Sequence Bottleneck**: Application servers generate IDs concurrently without sequence locking.

## 5. Implementation Compatibility & Developer Guidance

To prevent implementation ambiguity for future backend engineers, the following rules govern UUIDv7 usage:

1. **Generation Responsibility**: Primary key IDs MUST be generated in the **application layer** (Python service handlers or domain factories) using a standard UUIDv7 generator (`uuid6.uuid7()` or Python 3.13+ `uuid.uuid7()`) before persisting objects. This allows aggregate roots to construct child entity references in memory before executing database `flush()` or `commit()`.
2. **Database Storage Representation**: Column definitions use PostgreSQL native `uuid` data type (16 bytes binary storage, 36 characters string representation).
3. **SQLAlchemy 2.0 ORM Definition**: Models declare primary keys as:
   `id: Mapped[py_uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuidv7)`
4. **Scope & Exceptions**:
   - All 13 primary entity tables use UUIDv7 primary keys.
   - Natural external IDs (Meta WhatsApp `provider_message_id` / `wamid`, vehicle `vin`, human quote numbers `QT-2026-0042`) are stored as separate indexed `VARCHAR` columns alongside the UUIDv7 primary key.
5. **No Business Semantics from Primary Key Timestamps**:
   - Although UUIDv7 embeds a 48-bit UNIX millisecond timestamp for B-Tree index locality, business logic, API filters, and audit queries MUST NEVER extract timestamps from `id`.
   - All temporal query filtering MUST rely strictly on explicit `created_at TIMESTAMPTZ` and `updated_at TIMESTAMPTZ` columns.

---

## 6. Consequences

### Positive:
- High B-Tree insertion performance matching `BIGINT` while maintaining UUID security.
- Deterministic, standardized implementation contract for backend SQLAlchemy models.
- Clean native UUID representation in PostgreSQL (`uuid` data type, 16 bytes storage).

### Negative / Mitigation:
- Requires standard UUIDv7 generator utility in Python (`uuid6` or Python 3.13+ `uuid.uuid7()`).

