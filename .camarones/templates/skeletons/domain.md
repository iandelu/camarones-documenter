---
x-skeleton-for: domain/bounded-contexts.md
type: domain
title: <Bounded contexts | Actors | …>
description: Which bounded contexts the system has, which repo implements each one, and how they relate.
tags: [domain]
x-sources:
  - <repo>:<path>
---
# <Bounded contexts>

> **TL;DR:** <The contexts, which repos implement them, and the main relationships (customer/supplier, shared kernel…).>

## Contexts

| Context | Responsibility | Repos |
|---|---|---|
| <name> | <what it owns> | `<repo>` |

## Context map

```mermaid
flowchart LR
  A[<context>] -->|<relationship>| B[<context>]
```
