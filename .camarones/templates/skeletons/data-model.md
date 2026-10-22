---
type: data-model
title: <Store name> data model
description: Which tables or keys <store> holds, who writes and reads each one, and where the schema comes from.
tags: [<repo>, <store>]
x-sources:
  - <repo>:<path to migrations or entities>
---
# <Store name> data model

> **TL;DR:** <What the store holds, which service owns it, whether it is shared, and where its migrations live.>

## Entities

```mermaid
erDiagram
  <ENTITY> ||--o{ <OTHER> : <relation>
```

## Ownership

| Table / key | Writers | Readers |
|---|---|---|
| `<name>` | `<repo>` | `<repo>` |

## Migrations

<Liquibase/Flyway changelog path, or how the schema is created.>

## Shared access <!-- optional -->

<Only for a `#shared-db` store: who writes what, and the risk.>
