# QA plan: <short title>

Source: <ticket link, spec file, or "pasted by the user">
Build under test: <URL of the page or version endpoint that identifies the deployed build>

## Requirements

- R1: <one testable requirement, in the source's words> (source: <section, line, or screen>)

## Cases

| ID | Covers | Type | Steps | Expected | Oracle |
|---|---|---|---|---|---|
| C1 | R1 | api | <what to do, with concrete data> | <observable outcome: status, row count, text on screen> | <where the expected result comes from: spec section, DB rule, reference screen, product owner> |

## Risks

- <what could go wrong in production if this area is broken, and who would notice>

## Exit criteria

- E1: every case has a result, or is listed as not run with the command that was attempted
- E2: no suspected product bug remains open against a requirement in scope
