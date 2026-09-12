---
name: product
description: >-
  Use this skill when analyzing product requirements, validating feature alignment with the core MVP journey, enforcing business rules for car export between Europe and Tunisia (FCR, tax regimes), or protecting MVP scope boundaries.
---

# Product Analysis & Domain Rule Validation Skill

## 1. Purpose & Scope
Guide agents in analyzing user stories, validating feature requests against the target market (Europe to Tunisia automotive export), enforcing business domain rules, and protecting MVP scope boundaries.

## 2. Activation Triggers
Activate when analyzing feature requests, evaluating MVP scope, validating FCR customs eligibility rules, or checking business logic alignment.

## 3. Inspection Targets
- [`PRODUCT.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/PRODUCT.md) (Core promise & MVP scope control)
- [`docs/domain-model.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/docs/domain-model.md) (Domain entity models & state machine transitions)

## 4. Constraints
- **Core Promise Alignment**: Features must reinforce *"Never lose a customer because of a missed WhatsApp message."*
- **Human Authority Boundary**: AI features MUST NOT mutate financial quotes, vehicle availability, prices, or contracts without explicit human sales rep click/approval.
- **Strict MVP Scope Control**: Reject/defer features outside the defined core journey (e.g. crypto payments, port ship telemetry, ERP accounting).

## 5. Execution Procedure
1. Verify feature fit against target users (Europe-to-Tunisia car exporters, brokers, sales reps).
2. Validate Tunisia trade specifics (FCR privilege 5-year age limits, Netto/Brutto European VAT, shipping ports Rades/La Goulette).
3. Confirm human-in-the-loop approval remains mandatory for consequential business actions.
4. Flag any requested scope expansion that requires Human Approval Gate review.

## 6. Expected Outputs
- Domain validation report confirming feature alignment.
- Updated `docs/domain-model.md` if domain entities or states are modified.
