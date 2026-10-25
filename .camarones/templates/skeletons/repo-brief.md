---
type: overview
x-skeleton-for: repos/*/brief.md
title: <repo> brief
description: What <repo> does, its stack, how to build, test and run it, and the interfaces and data it owns.
tags: [<repo>]
x-sources:
  - <repo>:README.md
---
# <repo>

> **TL;DR:** <What the repo is for, in one line, plus its stack and how to run it.>

## Stack

| Language | Framework | Build tool | Versions |
|---|---|---|---|
| <Java 21> | <Spring Boot 3.3> | <Maven wrapper> | <from pom.xml> |

## Build, test and run

<!-- generated:commands repo=<repo> -->
<!-- /generated:commands -->

<Anything the generated table misses: profiles, seed data, how to reach a dependency.>

## Interfaces

The full lists of endpoints, topics and env vars are on the [<repo> page](index.md), generated from the code (`reference.md` in a project from before 4.52).

| Kind | Name | Evidence |
|---|---|---|
| <endpoint/listener/topic> | `<POST /path>` | `<repo>:<path>#L<a>-L<b>` |

## Data owned

<Stores and tables this repo writes, or "none".>

## Components

<The component view, from the C4 model.>

## Where the rest is <!-- optional -->

<Wiki, code graph and portal pages for this repo.>
