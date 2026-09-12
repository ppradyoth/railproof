# Contributing

Railproof is still in planning. Contributions should strengthen a stated security contract, test, or integration boundary.

## What a change needs

- one concrete problem
- one scoped implementation
- adversarial fixture
- benign control
- exact expected decision
- proof of whether the executor was reached
- documentation of failure modes

Detector output alone is not proof that an action was prevented.

## Security changes

Any change to policy precedence, approval binding, label propagation, canonical serialization, or executor behavior needs a regression test and a mutation test where supported.

Do not put real credentials, private prompts, employer details, or live external systems in fixtures.

## Public security reports

Do not open a public issue for a vulnerability that would expose users. GitHub private vulnerability reporting will be enabled before the repository is published.
