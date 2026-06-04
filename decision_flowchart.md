Decision Flowchart — High-level

This flowchart summarizes the decision-making pipeline used by the adjudication engine.

```mermaid
flowchart TD
  A[Start: Claim Created] --> B{Eligibility Checks}
  B -->|Fail: POLICY_INACTIVE / WAITING_PERIOD / MEMBER_NOT_COVERED| REJ1[Reject: Eligibility]
  B -->|Pass| C{Document Validation}
  C -->|Missing/Illegible docs| REJ2[Reject: Documentation]
  C -->|Pass| D{Coverage Check}
  D -->|Excluded / Service not covered| REJ3[Reject: Coverage]
  D -->|Pass| E{Limits Check}
  E -->|Per-claim/annual exceeded| REJ4[Reject: Limits]
  E -->|Pass| F{Medical Necessity}
  F -->|Insufficient diagnosis| REJ5[Reject: Medical]
  F -->|Pass| G{Fraud Flags}
  G -->|Fraud detected / low conf / high value| MANUAL[Refer for Manual Review]
  G -->|Pass| APPRO[Approve]
  REJ1 --> OUT[Decision Persisted]
  REJ2 --> OUT
  REJ3 --> OUT
  REJ4 --> OUT
  REJ5 --> OUT
  MANUAL --> OUT
  APPRO --> OUT
```

Decision output includes: `status`, `approved_amount`, `confidence_score`, `reasons`, and `policy_rules_checked`.
