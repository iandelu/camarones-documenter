---
type: guide
title: Runner propio para las propuestas de documentación
description: Cómo registrar una máquina vuestra como runner de GitHub o GitLab para que la propuesta de documentación con IA corra allí, con vuestra cuenta o modelo local, nunca con código de un fork.
x-owner: human
---
# Runner propio para las propuestas de documentación

> **TL;DR:** El job `docs-propose` ejecuta un agente, así que solo corre en una máquina que controláis. Registradla
> como runner, iniciad sesión con el agente en ella, poned `ci.target: self-hosted` en `workspace.yaml`, ejecutad
> `camaron ci` y copiad el job generado en cada repo de servicio. Alguien del proyecto etiqueta una PR con
> `docs:update` y el runner abre la PR de documentación.

## Cuándo hace falta

Sin runner, la misma propuesta corre en tu máquina: `camaron pr propose <url de la PR>`. El runner solo la hace
automática. La comprobación sin IA (`docs-fresh`) no necesita ningún runner vuestro.

## Qué necesita la máquina

| Qué | Para qué |
|---|---|
| git y uv (`curl -LsSf https://astral.sh/uv/install.sh \| sh`) | el job clona cam-docs y el kit y lo ejecuta con uv |
| La CLI del agente con sesión iniciada en la cuenta que paga: Claude Code, Codex u OpenCode con un modelo local | el agente es quien escribe |
| Un usuario dedicado, sin otros secretos | el job ejecuta el código de la PR: mantenlo lejos de todo lo demás |

## GitHub

1. Repo u organización → Settings → Actions → Runners → New self-hosted runner. Sigue los comandos que muestra en la
   máquina y dale las etiquetas que pondrás en `workspace.yaml` (por ejemplo `self-hosted, docs`).
2. Arráncalo como servicio (`./svc.sh install && ./svc.sh start`) con el usuario dedicado.
3. En cada repo de servicio: la variable `DOCS_REPO_URL` (la URL https de cam-docs) y el secreto `DOCS_WRITE_TOKEN`
   (puede subir ramas y abrir PRs en cam-docs).
4. Crea la etiqueta `docs:update`. Solo quien puede etiquetar (permiso triage o más) lanza el job, y nunca corre para
   PRs que vienen de un fork.

## GitLab

1. Grupo o proyecto → Settings → CI/CD → Runners → New runner, con una etiqueta (por ejemplo `docs-ai`); instala
   `gitlab-runner` en la máquina con el executor shell y regístralo con el token que te da.
2. En cada repo de servicio: las variables `DOCS_REPO_URL`, `DOCS_WRITE_TOKEN` (enmascarada: `write_repository` y
   `api` en cam-docs) y `DOCS_BOT_TOKEN` (enmascarada: `api` en ese repo, para comentar en la merge request).
3. Crea la etiqueta `docs:update`. El job se salta las merge requests que vienen de un fork.

## Activarlo

```yaml
# cam-docs/.camarones/workspace.yaml
ci:
  target: self-hosted
  runner_labels: [self-hosted, docs]     # runs-on de GitHub
  runner_tags: [docs-ai]                 # tags de GitLab
```

Después, `camaron ci` escribe `.camarones/ci/docs-propose.github.yml` (o `.gitlab-ci.yml`) junto a `docs-fresh`.
Cópialo en cada repo de servicio. Prueba antes una propuesta con `camaron pr propose <url de la PR> --dry-run` en el
runner.

## Seguridad

- El job solo corre para PRs etiquetadas del mismo repositorio: el código de un fork nunca llega a vuestra máquina.
- El token de cam-docs vive en el entorno del job, nunca en la configuración de git del runner.
- El agente escribe en una rama `docs/pr-<repo>-<n>`; nada llega a cam-docs sin que una persona fusione la PR.
