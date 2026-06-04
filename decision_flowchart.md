Decision Flowchart — High-level

This flowchart summarizes the decision-making pipeline used by the adjudication engine.

```mermaid
flowchart TD

A[Claim Submitted] --> B{Eligibility Checks}

B -->|Fail| REJ1[REJECTED]

B -->|Pass| C{Document Validation}

C -->|Missing / Invalid Documents| REJ2[REJECTED]

C -->|Pass| D{Coverage Check}

D -->|Not Covered / Excluded| REJ3[REJECTED]

D -->|Pass| E{Limits Check}

E -->|Limit Exceeded| REJ4[REJECTED]

E -->|Pass| F{Medical Necessity Check}

F -->|Insufficient Evidence| MANUAL[MANUAL REVIEW]

F -->|Pass| G{Fraud / Confidence Checks}

G -->|Low Confidence / Suspicious Claim| MANUAL

G -->|Pass| APPROVED[APPROVED]

REJ1 --> OUT[Decision Stored]
REJ2 --> OUT
REJ3 --> OUT
REJ4 --> OUT
MANUAL --> OUT
APPROVED --> OUT
```


Decision output includes: `status`, `approved_amount`, `confidence_score`, `reasons`, and `policy_rules_checked`.
