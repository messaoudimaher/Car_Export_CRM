# ADR 0004: Evolutionary Service Extraction Criteria

- **Status**: Approved
- **Date**: 2026-09-11
- **Deciders**: Lead Engineering Agent, Project Owner

---

## 1. Context & Problem Statement

Car-Export-CRM is built as a **Modular Monolith + Asynchronous Workers**. While the modular monolith is the initial architecture, team members or future requirements may consider extracting individual modules into independent microservices.

Premature microservice extraction increases operational complexity, deployment overhead, network latency, and distributed transaction bugs. Clear extraction criteria are needed.

---

## 2. Evolutionary Extraction Rule

> **RULE**: The system begins as a Modular Monolith. Service extraction of an individual module is permitted ONLY when justified by measurable operational metrics, an approved ADR, and explicit Human Approval Gate signoff.

---

## 3. Measurable Extraction Criteria

A module MAY be considered for extraction into an independent service ONLY if at least two of the following criteria are met:

1. **Scaling Asymmetry**: The module requires > 10x compute/memory scaling compared to core API servers (e.g. heavy AI media/voice processing).
2. **Independent Deployment Lifecycle**: The module is maintained by a separate engineering team requiring independent deployment pipelines.
3. **Reliability Isolation**: Failure in the module (e.g. third-party integration crash) threatens core API availability despite circuit breaker patterns.
4. **Technology Runtime Constraint**: The module requires a specialized programming language or hardware runtime (e.g. C++ binary or GPU inference node).

---

## 4. Required Process for Extraction

1. Measure baseline performance/scaling metrics.
2. Submit ADR detailing proposed microservice boundaries, gRPC/HTTP API contracts, and async message queue protocol.
3. Obtain explicit signoff via **Human Approval Gate #2**.
