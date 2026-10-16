---
type: deployment
title: Environments
description: Which environments exist, where each service runs, how it is deployed and where its configuration and secrets come from.
tags: [deployment]
x-sources:
  - <repo>:<path to Helm, K8s, compose or pipeline>
---
# Environments

> **TL;DR:** <The environments, the platform they run on, and how a change reaches production.>

## Environments

| Environment | URL | Platform | Deployed by |
|---|---|---|---|
| <dev> | <https://…> | <k8s, VM…> | <pipeline> |

## Infrastructure source

<Helm charts, K8s manifests, ArgoCD apps or compose files, with paths.>

## Configuration and secrets

<Where configuration and secrets come from in each environment (never the values).>
