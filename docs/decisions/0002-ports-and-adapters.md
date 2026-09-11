# ADR 0002: Ports and Adapters Architecture for External Integrations

- **Status**: Approved
- **Date**: 2026-09-11
- **Deciders**: Lead Engineering Agent, Project Owner

---

## 1. Context & Problem Statement

Car-Export-CRM requires integration with external infrastructure services including WhatsApp messaging APIs (Meta Cloud API), LLMs (OpenAI, Anthropic), Embedding models, and Object Storage (S3, local disk).

Directly importing third-party provider SDKs or concrete HTTP client code inside domain or application modules creates tight coupling, hinders unit testing, makes provider swapping difficult, and risks exposing provider credential details throughout application code.

---

## 2. Decision Drivers

- **Domain Isolation**: Core business logic must remain independent of external vendor SDKs.
- **Testability**: Fast unit and integration testing requires easy substitution of mock provider doubles (`MockWhatsAppProvider`, `MockLLMProvider`).
- **Pluggability**: Ability to swap infrastructure providers (e.g. Meta Cloud API to Twilio, or OpenAI to Anthropic/Ollama) without modifying application code.

---

## 3. Considered Options

1. **Option 1**: Direct Vendor SDK Imports (Directly calling `facebook-sdk` or `openai` inside service handlers).
2. **Option 2**: Microservices Wrapper (Building standalone HTTP microservices for each external service).
3. **Option 3**: Ports & Adapters (Hexagonal Architecture) within the Modular Monolith.

---

## 4. Decision Outcome

**Chosen Option**: **Option 3: Ports & Adapters**.

### Specifications:
- **Port Interfaces**: Abstract Python classes (`ABC`) defined in `src/backend/app/ports/` (e.g. `WhatsAppProvider`, `LLMProvider`, `EmbeddingProvider`, `ObjectStorageProvider`).
- **Infrastructure Adapters**: Concrete implementations placed in `src/backend/app/adapters/` (e.g. `MetaCloudApiAdapter`, `OpenAIAdapter`, `S3StorageAdapter`).
- **Dependency Injection**: FastAPI dependency injection supplies concrete adapter instances based on configuration settings.

### Consequences:
- **Positive**: Core domain logic remains 100% vendor agnostic. Unit tests run fast using mock doubles.
- **Negative**: Requires writing small abstract interface wrappers for every third-party integration.
