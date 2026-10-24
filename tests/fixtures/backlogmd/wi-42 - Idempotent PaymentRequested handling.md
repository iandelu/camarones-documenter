---
id: WI-42
title: Idempotent PaymentRequested handling
status: Ready
assignee:
  - ana
created_date: '2026-10-24 10:12'
labels:
  - payments
dependencies:
  - WI-40
documentation:
  - FLOW-k3f9#retries@1a2b3c4d
  - DEC-0004
parent_task_id: WI-3
priority: P1
type: story
ordinal: 3000
x-uid: 01jb7q3m
x-repos:
  - payments
x-jira: PAY-118
---

## Description
<!-- SECTION:DESCRIPTION:BEGIN -->
As … I want … so that …
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A duplicate message has no second effect
- [ ] #2 After 3 retries the message goes to the DLQ
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 acceptance criteria met
<!-- DOD:END -->
