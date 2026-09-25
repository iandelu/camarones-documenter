"""Camarón 🦐 — interactive project-documentation wizard (macOS / Windows / Linux terminal)."""
from __future__ import annotations

import os, platform, random, subprocess, sys, time
from pathlib import Path

import questionary
from questionary import Choice, Separator, Style
from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings
from rich import box
from rich.console import Console, Group
from rich.live import Live
import threading
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Table
from rich.text import Text

from .common import (ROOT, HOME, WORK, WS_FILE, CACHE, IS_WIN, IS_MAC, CAM_DIR, CAM_LAYOUT, WORKSPACE, which, cli_cmd,
                     load_json, save_json, out, repo_dir)
from . import docs, env, plan, creds, quickarch, radar, tutorial
from .common import VERSIONS, ws_rel
from rich.tree import Tree
import webbrowser

console = Console(highlight=False)
PREFS = HOME / ".camarones.json"
MODELS = ["sonnet", "opus", "haiku"]           # Claude Code's --model aliases; the default is set in do_model / launch_agent
CODEX_MODEL_DEFAULT = "gpt-5.6-terra"          # Codex's model slugs rotate, so this is just a starting default, not a fixed list
FIRSTRUN = CACHE / "firstrun.json"     # first-run wizard position (so closing the window never loses it)
STEPS = ("name", "repos", "tools", "setup", "stack", "arch", "intro")   # first-run steps, saved by id
LEGACY_STEPS = ("name", "repos", "tools", "setup", "arch", "intro")     # firstrun.json before 3.3 kept only the index
ORANGE = "#ff7a2f"
BACK = "__back__"   # questionary replaces a None value with the title, so use a sentinel
EXTRA_REVIEWS = {   # opt-in unit types: uid -> deps required to be `done` before offering it
    "security-review": ["arch-system", "domain", "data", "deployment"],
    "architecture-review": ["arch-system", "domain", "data", "deployment", "decisions-quality"],
}
STYLE = Style([("qmark", f"fg:{ORANGE} bold"), ("pointer", f"fg:{ORANGE} bold"), ("highlighted", f"fg:{ORANGE} bold"),
               ("selected", f"fg:{ORANGE}"), ("answer", f"fg:{ORANGE} bold"), ("question", "bold"),
               ("separator", "fg:#8a8a8a"), ("instruction", "fg:#8a8a8a italic"), ("disabled", "fg:#6c6c6c italic")])

CAMARON = r"""
[#ff7a2f]  ⠀⠀⠀⠀⠘⠒⠖⠲⠒⠖⠲⠒⠖⠲⠒⠖⠲⢤⣀⠀[/]
[#ff7a2f]  ⠀⠀⠀⣀⣴⠦⠠⣤⠤⠤⠤⠤⠤⠤⠤⠤⠤⣤⠈⣆[/]
[#ff7a2f]  ⠀⣰⡾⠋⠀⠀⠀⣻⠀⠀⠀⠀⣖⣳⠀⠀⠀⣽⠀⣸[/]
[#ff7a2f]  ⣰⠏⠖⣀⠀⠀⠀⣯⠀⠀⠀⠀⠀⠀⠀⠀⣰⢃⡴⠃[/]
[#ff7a2f]  ⡇⠀⠀⠈⣳⣄⢀⡽⢤⡤⢤⡤⣤⠤⠔⠚⠉⠁⠀⠀[/]
[#ff7a2f]  ⢭⣀⣀⡀⢠⠎⠛⠀⠀⠀⡎⠱⡌⢢⠀⠀⠀⠀⠀⠀[/]
[#ff7a2f]  ⣽⠀⠀⠀⣇⠀⠀⠀⠀⠀⠇⠀⠇⠸⠀⠀⠀⠀⠀⠀[/]
[#ff7a2f]  ⢻⣦⡠⠐⣇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]
[#ff7a2f]  ⠀⠈⠳⣎⠙⠢⣄⠀⠀⢀⣤⠴⡶⠀⠀⠀⠀⠀⠀⠀[/]
[#ff7a2f]  ⠀⠀⠀⠈⠓⠶⠤⣉⣹⣁⣀⣋⣧⠀⠀⠀⠀⠀⠀⠀[/]
"""

T = {
    "es": {
        "tagline": "Camarón que se duerme, se lo lleva la corriente — documentación que no se queda atrás.",
        "busy": ["Pelando repos…", "Cociendo el grafo…", "El camarón está sudando…", "Hirviendo el portal…",
                 "Echando sal al C4…", "Rebozando la documentación…"],
        "welcome": "¡Bienvenido a Camarón! Te guío paso a paso: primero el entorno, luego sesiones cortas con tu IA "
                   "(Claude Code o Codex) que documentan el proyecto por partes y guardan el progreso.",
        "step": "Paso {n} de {t}",
        "project_name": "¿Cómo se llama el proyecto?",
        "found_repos": "He encontrado estos repos en la carpeta:",
        "use_found": "¿Los uso?",
        "add_url": "URL git de otro repo para clonar (vacío para terminar):",
        "repo_name": "Nombre de carpeta para ese repo:",
        "branch": "Rama:",
        "no_repos": "No hay repos todavía. Añade al menos uno (URL) o copia los repos en esta carpeta y vuelve a abrir Camarón.",
        "prereq": "Comprobando requisitos",
        "missing": "Falta {what}. ¿Lo instalo ahora?",
        "reopen": "Instalado. Cierra y vuelve a abrir Camarón para que el sistema lo detecte.",
        "manual": "Instálalo a mano y vuelve a abrir Camarón: {hint}",
        "setup_run": "Instalando herramientas, repos y conectando Claude/Codex (tarda unos minutos la primera vez)",
        "setup_ok": "Entorno listo 🦐",
        "pointer_ask": "¿Añado a cada repo un aviso corto en su CLAUDE.md apuntando a cam-docs? (se añade al final, "
                       "nunca borra nada; sin él los agentes abiertos dentro de un repo no ven la documentación)",
        "migrate_ask": "Este proyecto usa la estructura antigua (docs y config en la raíz y dentro de cada repo). "
                       "¿Lo paso a {cam}/ ahora? Verás la lista de cambios antes de confirmar.",
        "sessions_intro": "Ahora el trabajo va por sesiones: cada una hace UNA unidad del plan (p. ej. analizar un repo). "
                          "Al acabar, la IA guarda el progreso y te pregunta qué seguir. Tú vuelves aquí → «Siguiente paso».",
        "menu": "¿Qué hacemos?",
        "m_next": "🦐 Siguiente paso (sesión con IA)",
        "m_plan": "📋 Plan de trabajo",
        "m_redo": "↻ Rehacer un paso ya hecho (p. ej. una entrevista)",
        "rd_none": "Todavía no hay ningún paso terminado que rehacer.",
        "rd_pick": "¿Qué paso quieres rehacer? La IA revisará lo que hay y lo actualizará (no se borra nada).",
        "rd_deps": "Estos pasos ya hechos se basan en «{u}». Marca los que quieras rehacer también (↩ ninguno):",
        "rd_ok": "«{u}» vuelve a estar pendiente (rehacer).",
        "rd_now": "¿Empezamos ahora?",
        "m_setup": "🛠  Instalar / reparar entorno",
        "m_repos": "📦 Repos",
        "m_confirm": "✅ Revisar y confirmar páginas",
        "m_portal": "🌐 Portal",
        "m_status": "🔎 Estado de la documentación",
        "m_ci": "⚙️  CI (GitLab / GitHub)",
        "m_extra": "➕ Revisiones extra (seguridad, arquitectura) — beta",
        "m_update": "🔄 Actualizar doc tras cambios (sesión con IA)",
        "m_model": "🧠 Modelo de IA",
        "m_lang": "🌍 Idioma / Language",
        "m_exit": "🚪 Salir",
        "extra_pick": "Marca las revisiones opcionales que quieres añadir al plan (beta — revisa sus hallazgos con ojo crítico; espacio para marcar):",
        "extra_need": "necesita arch-system/domain/data/deployment",
        "extra_added": "{n} revisión(es) añadida(s) al plan.",
        "extra_already": "ya está en el plan",
        "bye": "¡Hasta la próxima! Camarón que se duerme… 🦐",
        "ready_units": "Unidades listas para hacer:",
        "autopilot": "▶▶ Piloto automático: encadenar unidades sin preguntar (Claude Code + Codex)",
        "autopilot_info": ("Ejecuta las unidades listas una tras otra, cada una en una sesión nueva y desatendida. Si Claude "
                           "o Codex llegan a su límite de uso cambia al otro, y si ambos lo alcanzan espera y reintenta "
                           "(deja el equipo encendido). Se salta las entrevistas y los pasos del asistente; las dudas "
                           "quedan en docs/interview/open-questions.md."),
        "autopilot_bg": "Piloto automático en marcha en otra ventana. Registro: docs/.work/log.md. Ctrl+C allí para pararlo.",
        "all_done": "¡Plan completado! Usa «Actualizar doc tras cambios» cuando haya cambios en el código.",
        "which_agent": "¿Con qué agente?",
        "which_model_agent": "¿Modelo de qué agente quieres ajustar?",
        "which_model": "¿Qué modelo de Claude uso por defecto?",
        "which_codex_model": "¿Qué modelo de Codex uso por defecto? (puedes escribir cualquier slug válido)",
        "model_set": "✔ Modelo por defecto: {model}",
        "copy_prompt": "📋 Copiar el prompt (lo pego yo)",
        "launching": "Abriendo {agent}. Cuando termine la sesión, vuelve aquí.",
        "launched_bg": "🦐 Se abrió en una ventana nueva. Este menú sigue disponible: revisa «📋 Plan» o «🔎 Estado» para ver el progreso.",
        "copied": "Prompt copiado al portapapeles y guardado en docs/.work/next-prompt.md",
        "saved_prompt": "Prompt guardado en docs/.work/next-prompt.md",
        "after": "Sesión terminada. Progreso: {d}/{t}.",
        "back": "↩ Volver",
        "nothing_confirm": "No hay páginas pendientes de confirmar.",
        "pick_confirm": "Marca las páginas que has revisado y das por buenas (espacio para marcar):",
        "your_name": "Tu nombre (queda registrado en la confirmación):",
        "confirmed_n": "{n} páginas confirmadas.",
        "p_live": "📝 Abrir el portal (docs, revisión, C4, grafo de código, wikis — editable)", "p_build": "📦 Exportar el portal para desplegar (solo lectura, CI / hosting)", "p_up": "🐳 Servir la exportación con Docker", "p_open": "Abrir en el navegador", "p_down": "Parar",
        "m_wikis": "📚 Wikis (OpenWiki)", "w_title": "Wikis por repo", "w_pages": "{n} páginas", "w_none": "sin wiki", "w_stale": "desactualizada",
        "w_pick": "¿Qué repos genero / actualizo?", "w_engine": "¿Quién escribe la wiki?", "w_open": "🌐 Verlas en el portal",
        "w_gen": "✨ Generar / actualizar wikis", "w_eng_openwiki": "OpenWiki (clave de proveedor guardada)",
        "w_eng_claude": "Claude Code (sin terminal, con las herramientas MCP de OpenWiki)", "w_eng_codex": "Codex (sin terminal, con las herramientas MCP de OpenWiki)",
        "w_no_engine": "OpenWiki no puede lanzarse sin terminal todavía. Guarda una clave una vez con `openwiki auth configure openai` (o anthropic, gemini, openrouter), o instala Claude Code / Codex.",
        "w_done": "Wiki lista: {repo}", "w_fail": "La wiki de {repo} falló — el motivo está en la línea ⚠ de arriba",
        "w_off": "sin wiki (no elegido)", "w_need_brief": "antes: su repo-brief (INSTRUCTIONS.md)",
        "w_choose": "🎯 Elegir qué repos tienen wiki", "w_choose_first": "elige antes los repos",
        "w_choose_q": "¿Qué repos llevan wiki? Cada una es una sesión de agente completa: elige los servicios con lógica, no librerías ni repos de CI",
        "w_none_chosen": "Ningún repo tiene wiki todavía: elige primero cuáles (🎯).", "w_skipped": "No lanzados: {repos}", "w_unit_q": "¿Cómo generas la wiki de {repo}?",
        "w_none_ready": "Ningún repo elegido está listo para wiki ({repos}): antes necesitan su repo-brief (INSTRUCTIONS.md). Hazlo desde el plan.",
        "w_here": "✨ Aquí mismo (sin sesión de agente, {engine})", "w_agent": "🤖 Sesión de agente interactiva",
        "port": "Puerto:",
        "r_detect": "Detectar repos en la carpeta", "r_add": "Añadir repo por URL", "r_sync": "Sincronizar (clone / pull)",
        "r_remove": "Quitar repo del proyecto",
        "ci_forge": "¿Dónde viven los repos?",
        "ci_done": "Pipeline instalado. Variables necesarias en el tutorial (docs/guides/tutorial.md §8).",
        "error": "Algo falló:",
        "install_here": "Estás dentro de «{kit}». ¿Instalo Camarón en la carpeta del proyecto «{parent}»?",
        "installed_here": "Instalado en {parent}. Abre Camarón desde allí (camaron.command / camaron.cmd).",
        "no_tty": "Camarón necesita una terminal interactiva. Usa los comandos: {cli} help",
        "unit_wizard": "Esta unidad la hace el propio asistente.",
        "nav_select": "↑↓ moverse · Enter elegir · Esc volver",
        "nav_check": "↑↓ moverse · Espacio marcar/desmarcar · a todos/ninguno · Enter confirmar · Esc volver",
        "nav_text": "(Enter aceptar · Esc volver)",
        "nav_confirm": "(s/n · Esc volver)",
        "repos_title": "Repos del proyecto",
        "repos_none": "(todavía ninguno)",
        "r_continue": "✔ Continuar con estos repos",
        "r_pick": "Elegir entre los repos de la carpeta",
        "r_need": "añade al menos un repo",
        "prereq_continue": "✔ Continuar",
        "prereq_retry": "↻ Volver a comprobar",
        "prereq_blocked": "faltan requisitos obligatorios",
        "go_menu": "🦐 Ir al menú principal",
        "setup_again": "↻ Repetir instalación",
        "exit_q": "¿Salir de Camarón?",
        "pick_remove": "Marca los repos que quieres quitar:",
        "k_menu": "🔑 Tokens GitLab / GitHub",
        "k_title": "Tokens guardados",
        "k_none": "Sin tokens guardados.",
        "k_add": "Añadir / actualizar un token",
        "k_del": "Borrar un token",
        "k_test": "Probar tokens",
        "k_host": "Servidor (p. ej. gitlab.com, github.com o gitlab.tuempresa.com):",
        "k_kind": "¿Qué es?",
        "k_token": "Token (no se muestra al escribir):",
        "k_scopes": "GitLab: token personal con 'read_api' + 'read_repository' (y 'write_repository' si quieres que Camarones haga push). GitHub: token fine-grained con 'Contents: read' (y 'Metadata').",
        "k_privacy": "🔒 Se guarda en el llavero del sistema ({where}). Nunca se escribe en el proyecto, ni en git config, ni se pasa a Claude/Codex: solo lo usa Camarones para clonar/actualizar repos y listar proyectos.",
        "k_ok": "✔ Token válido: conectado como {user}",
        "k_bad": "✖ El servidor rechazó el token: {err}",
        "k_save_anyway": "¿Guardarlo igualmente?",
        "k_saved": "✔ Token guardado para {host}",
        "k_pick_del": "¿Cuál borro?",
        "r_remote": "Añadir desde GitLab / GitHub (con token)",
        "r_scope": "Grupo de GitLab u organización de GitHub (vacío = todos los repos a los que tienes acceso):",
        "r_listing": "Buscando proyectos…",
        "r_pick_remote": "Marca los repos a añadir:",
        "r_none_remote": "No he encontrado proyectos con ese token/grupo.",
        "r_which_host": "¿De qué servidor?",
        "r_new_host": "➕ Otro servidor / nuevo token",
        "s_missing": "⚠ No se han podido clonar: {repos}. Suele ser por falta de permisos: añade un token.",
        "s_token_retry": "🔑 Añadir token de GitLab/GitHub y reintentar",
        "a_menu": "🏗 Diagrama rápido de arquitectura",
        "a_title": "Primer vistazo a la arquitectura (análisis estático, sin IA)",
        "a_question": "¿Está bien? ¿Lo guardo?",
        "a_save": "✔ Está bien, guárdalo",
        "a_open": "🌐 Verlo interactivo en el navegador",
        "a_ai": "✨ Guardarlo y mejorarlo ahora con IA",
        "a_again": "↻ Volver a analizar",
        "a_skip": "✖ No lo guardes, sigo sin él",
        "a_overwrite": "Ya hay un modelo C4 en docs/architecture. ¿Lo sustituyo por este borrador?",
        "a_saved": "✔ Guardado como borrador en docs/architecture (el plan lo irá refinando)",
        "a_invalid": "⚠ LikeC4 encontró errores en el borrador; puedes guardarlo y la IA lo corregirá.",
        "a_users": "usan",
        "a_done": "El diagrama rápido ya está hecho (guardado el {when}). ¿Qué quieres hacer?",
        "a_view": "🌐 Verlo en el portal (pestaña C4)",
        "a_redo": "↻ Rehacerlo (volver a analizar los repos)",
        "a_keep": "✔ Dejarlo como está",
        "sk_menu": "🧰 Stack y herramientas de cada repo",
        "sk_intro": "He mirado cada repo sin IA: su stack y las herramientas que ya usáis (Backstage, Sonar, librería de componentes, linters, contratos, CI…). La IA lo leerá primero y lo irá afinando. Si un stack está mal, corrígelo aquí.",
        "sk_repo": "Repo", "sk_stack": "Stack", "sk_tools": "Herramientas detectadas",
        "sk_detected": "detectado",
        "sk_none": "Aún no hay repos descargados: lo analizaré cuando estén (menú → Stack y herramientas).",
        "sk_question": "¿Es correcto?",
        "sk_ok": "✔ Correcto, seguir",
        "sk_fix": "✏ Corregir el stack de un repo",
        "sk_view": "🌐 Ver la página en el portal",
        "sk_pick": "¿Qué repo?",
        "sk_fix_q": "Stack de {repo} (vacío = el detectado):",
        "sk_done": "✔ Apuntado. Ya sé qué hay en vuestra caja de herramientas: nada de pescar a ciegas 🦐",
        "up_found": "Hay una versión nueva del kit: v{new} (este proyecto usa v{cur}).\nEncontrada en: {where}",
        "up_q": "¿Actualizo ahora? (se conservan tu configuración, el plan y toda la documentación)",
        "up_done": "✔ Actualizado a v{new}. Reiniciando…",
        "fr_resumed": "Retomo la instalación donde la dejaste.",
        "m_resume": "▶ Continuar «{u}» (se quedó a medias)",
        "m_review": "✅ Revisar y verificar páginas",
        "m_tutorial": "📖 Tutorial: ¿qué es cada herramienta?",
        "m_uninstall": "🧹 Deshacer todo (quitar la documentación de este proyecto)",
        "u_global": "¿Limpiar también lo de tu usuario? (~/.camarones, tokens guardados, ajustes del wizard — lo comparten todos tus proyectos)",
        "u_preview": "Esto es lo que se va a quitar",
        "u_keep": "No se toca",
        "u_confirm": "Escribe el nombre del proyecto ({name}) para confirmar:",
        "u_cancel": "Cancelado: no se ha borrado nada.",
        "u_done": "✔ Hecho: {ws} vuelve a tener solo sus repos, tal como estaban.",
        "u_backup": "Copia de seguridad de cam-docs: {path}",
        "d_doing": "En curso", "d_last": "último checkpoint", "d_fb": "correcciones tuyas pendientes",
        "k_doing": "En curso", "k_todo": "Por hacer", "k_blocked": "Bloqueadas", "k_done": "Hechas", "k_ready": "← lista",
        "res_q": "«{u}» se quedó a medias. ¿Cómo sigo?",
        "res_new": "▶ Nueva sesión que retoma desde el último checkpoint (recomendado)",
        "res_cont": "💬 Reabrir la última conversación de {agent}",
        "res_done": "✔ Ya está terminada: márcala como hecha",
        "res_restart": "↺ Empezar esta unidad de cero",
        "still_doing": "La unidad sigue a medias. Lo escrito está guardado: la próxima vez elige «▶ Continuar» y la IA retoma desde el último checkpoint.",
        "saved_ckpt": "💾 Progreso guardado (commit local en la carpeta del proyecto, sin push).",
        "rv_title": "✅ Revisar y verificar",
        "rv_intro": "La IA escribe borradores; tú decides qué es verdad. Te enseño las páginas una a una (primero las más importantes):\n\n"
                    "  ✔ [bold]Está bien[/] → la página queda [green]confirmada[/]: las IAs la usan como fuente de verdad y no la reescriben sin avisar; "
                    "el portal la marca como verificada. Si alguien la cambia después, vuelve a ⚠️ re-confirmar.\n"
                    "  ✏️  [bold]Hay algo mal[/] → escribes qué falla (en tus palabras). Se guarda en docs/.work/review-feedback.md y la unidad "
                    "«Aplicar tus correcciones» aparece en «Siguiente paso» para que la IA lo arregle.\n"
                    "  ⏭ [bold]Saltar[/] → la dejas para otro día.",
        "rv_none": "No hay nada pendiente de revisar 🎉",
        "rv_count": "{n} páginas por revisar · {r} cambiaron desde que se confirmaron",
        "rv_start": "▶ Empezar",
        "rv_head": "Página {i} de {n}",
        "rv_draft": "✨ borrador de la IA", "rv_reconf": "⚠️ cambió desde que se confirmó",
        "rv_q": "¿Qué te parece esta página?",
        "rv_confirm": "✔ Está bien → confirmar",
        "rv_change": "✏️  Hay algo mal → pedir cambios",
        "rv_full": "📖 Leer entera",
        "rv_es": "🇪🇸 Ver la traducción al español", "rv_en": "🇬🇧 Ver el original (inglés)",
        "rv_skip": "⏭ Saltar",
        "rv_stop": "⏹ Terminar la revisión",
        "rv_what": "¿Qué está mal o falta? (la IA lo corregirá)",
        "rv_more": "… {n} líneas más → «📖 Leer entera»",
        "rv_showing_es": "Mostrando la traducción al español (se confirma la página original).",
        "rv_sum": "Revisión: ✔ {c} confirmadas · ✏️ {f} con cambios pedidos · ⏭ {s} saltadas",
        "rv_fix_now": "✨ Aplicar tus correcciones ahora con IA",
        "rv_later": "Luego (aparece en «Siguiente paso»)",
        "st_title": "🔎 Estado de la documentación",
        "st_legend": "✅ confirmada por una persona · ✨ borrador de la IA · ⚠️ confirmada pero cambió después · "
                     "huérfana = cita código que ya no existe · traducción = español que falta o se quedó atrás",
        "st_problems": "Qué hay que hacer",
        "st_ok": "✔ Todo en orden: nada que arreglar.",
        "st_err": "{n} errores de formato/enlaces (check)",
        "st_orph": "{n} páginas citan código que ya no existe",
        "st_reconf": "{n} páginas confirmadas cambiaron: revísalas",
        "st_draft": "{n} borradores sin revisar",
        "st_i18n": "{n} traducciones faltan o están desactualizadas",
        "st_fb": "{n} correcciones tuyas sin aplicar",
        "st_changes": "{n} repos con cambios de código sin documentar",
        "st_fix": "✨ Arreglar los problemas con IA (errores, huérfanas, traducciones)",
        "st_review": "✅ Revisar páginas ({n})",
        "st_apply": "✨ Aplicar tus correcciones ({n})",
        "st_update": "🔄 Documentar los cambios del código ({n} repos)",
        "st_list": "📄 Ver todas las páginas",
        "p_local": "🐍 Servir la exportación sin Docker",
        "p_docker_na": "Docker no está disponible ({why}). ¿Lo sirvo sin Docker?",
        "p_running": "Portal en marcha: {url}",
        "p_docker_fail": "Docker no pudo levantarlo. ¿Lo sirvo sin Docker mientras tanto?",
        "tu_title": "📖 Tutorial", "tu_next": "▶ Siguiente", "tu_prev": "◀ Anterior", "tu_index": "📑 Índice",
        "tu_done": "✔ Entendido, al menú", "tu_offer": "📖 Ver el tutorial (2 minutos): qué es cada herramienta",
        "facts": [
            "🦐 ¿Sabías que…? El corazón de las gambas está en la cabeza.",
            "🦐 ¿Sabías que…? La gamba mantis tiene entre 12 y 16 tipos de fotorreceptores; tú tienes 3.",
            "🦐 ¿Sabías que…? El golpe de la gamba mantis es tan rápido que hace hervir el agua (cavitación).",
            "🦐 ¿Sabías que…? La gamba pistola cierra la pinza y suelta un chasquido de más de 200 decibelios.",
            "🦐 ¿Sabías que…? El camarón cocido es rosa por la astaxantina, que el calor libera de sus proteínas.",
            "🦐 ¿Sabías que…? Los camarones limpiadores montan 'estaciones' donde los peces hacen cola para desparasitarse.",
            "🦐 ¿Sabías que…? Para huir, las gambas nadan hacia atrás doblando el abdomen de golpe.",
            "🦐 ¿Sabías que…? El krill antártico es una de las especies con más biomasa del planeta.",
            "🦐 ¿Sabías que…? La gamba mantis no es gamba ni mantis: es un estomatópodo.",
            "🦐 ¿Sabías que…? Algunas gambas nacen macho y se convierten en hembra con los años.",
            "🦐 ¿Sabías que…? Los cangrejos ermitaños hacen cola por tallas para intercambiarse conchas.",
            "🦐 Camarón que se duerme, se lo lleva la corriente… por eso guardamos el progreso.",
            "🦐 Si esto va lento no es el camarón: es npm descargando medio internet.",
            "🦐 Pelando repos con cariño, sin romper ni un commit.",
            "🦐 Un buen C4 es como un buen caldo: se hace con paciencia.",
        ],
        "elapsed": "transcurrido",
        "t_title": "Herramientas",
        "t_required": "obligatorio", "t_optional": "opcional", "t_kit": "Camarones",
        "t_installed": "instalado", "t_missing": "falta",
        "t_all": "✔ Instalar todo lo recomendado (recomendado)",
        "t_pick": "Elegir qué instalar",
        "t_none": "Continuar sin instalar nada más",
        "t_pick_q": "Marca lo que quieres instalar / activar:",
        "t_need_req": "faltan git o Node.js: son obligatorios",
        "t_installing": "Instalando lo que falta del sistema",
        "agent_one_ok": "opcional — con {other} es suficiente",
        "agent_none": "sin agente: podrás copiar los prompts, pero instala Claude Code o Codex para las sesiones",
        "java_sdkman": "Java no está activo en esta terminal pero tienes SDKMAN: se usará ~/.sdkman/candidates/java/current",
    },
    "en": {
        "tagline": "The sleeping shrimp gets carried away by the current — docs that keep up.",
        "busy": ["Peeling repos…", "Boiling the graph…", "The shrimp is sweating…", "Simmering the portal…",
                 "Salting the C4 model…", "Battering the docs…"],
        "welcome": "Welcome to Camarón! I'll guide you step by step: first the environment, then short sessions with "
                   "your AI (Claude Code or Codex) that document the project piece by piece and save progress.",
        "step": "Step {n} of {t}",
        "project_name": "Project name?",
        "found_repos": "I found these repos in this folder:",
        "use_found": "Use them?",
        "add_url": "Git URL of another repo to clone (empty to finish):",
        "repo_name": "Folder name for that repo:",
        "branch": "Branch:",
        "no_repos": "No repos yet. Add at least one URL, or copy the repos into this folder and reopen Camarón.",
        "prereq": "Checking prerequisites",
        "missing": "{what} is missing. Install it now?",
        "reopen": "Installed. Close and reopen Camarón so your system picks it up.",
        "manual": "Install it manually and reopen Camarón: {hint}",
        "setup_run": "Installing tools, repos and wiring Claude/Codex (a few minutes the first time)",
        "setup_ok": "Environment ready 🦐",
        "pointer_ask": "Add a short note to each repo's CLAUDE.md pointing at cam-docs? (appended at the end, never "
                       "removes anything; without it agents opened inside a repo don't see the docs)",
        "migrate_ask": "This project uses the old layout (docs and config at the root and inside every repo). "
                       "Move it to {cam}/ now? You'll see the list of changes before confirming.",
        "sessions_intro": "From now on work happens in sessions: each one does ONE plan unit (e.g. analyze a repo). When it "
                          "finishes, the AI saves progress and asks what next. You come back here → “Next step”.",
        "menu": "What shall we do?",
        "m_next": "🦐 Next step (AI session)",
        "m_plan": "📋 Work plan",
        "m_redo": "↻ Redo a finished step (e.g. an interview)",
        "rd_none": "No finished step to redo yet.",
        "rd_pick": "Which step do you want to redo? The AI reviews what is there and updates it (nothing is deleted).",
        "rd_deps": "These finished steps build on “{u}”. Tick the ones to redo as well (↩ none):",
        "rd_ok": "“{u}” is pending again (redo).",
        "rd_now": "Start it now?",
        "m_setup": "🛠  Install / repair environment",
        "m_repos": "📦 Repos",
        "m_confirm": "✅ Review & confirm pages",
        "m_portal": "🌐 Portal",
        "m_status": "🔎 Documentation status",
        "m_ci": "⚙️  CI (GitLab / GitHub)",
        "m_extra": "➕ Extra reviews (security, architecture) — beta",
        "m_update": "🔄 Update docs after changes (AI session)",
        "m_model": "🧠 AI model",
        "m_lang": "🌍 Idioma / Language",
        "m_exit": "🚪 Exit",
        "extra_pick": "Tick the optional reviews you want to add to the plan (beta — verify their findings critically; space to tick):",
        "extra_need": "needs arch-system/domain/data/deployment",
        "extra_added": "{n} review(s) added to the plan.",
        "extra_already": "already in the plan",
        "bye": "See you! 🦐",
        "ready_units": "Units ready to do:",
        "autopilot": "▶▶ Autopilot: chain units without asking (Claude Code + Codex)",
        "autopilot_info": ("Runs the ready units one after another, each in a fresh unattended session. If Claude or Codex "
                           "hits its usage limit it switches to the other, and if both do it waits and retries (leave the "
                           "machine on). Interviews and wizard steps are skipped; questions go to "
                           "docs/interview/open-questions.md."),
        "autopilot_bg": "Autopilot running in another window. Log: docs/.work/log.md. Ctrl+C there to stop it.",
        "all_done": "Plan complete! Use “Update docs after changes” when the code changes.",
        "which_agent": "Which agent?",
        "which_model_agent": "Which agent's model do you want to set?",
        "which_model": "Which Claude model should be the default?",
        "which_codex_model": "Which Codex model should be the default? (type any valid slug)",
        "model_set": "✔ Default model: {model}",
        "copy_prompt": "📋 Copy the prompt (I'll paste it)",
        "launching": "Opening {agent}. Come back here when the session ends.",
        "launched_bg": "🦐 Opened in a new window. This menu stays available — check “📋 Plan” or “🔎 Status” to see progress.",
        "copied": "Prompt copied to clipboard and saved to docs/.work/next-prompt.md",
        "saved_prompt": "Prompt saved to docs/.work/next-prompt.md",
        "after": "Session finished. Progress: {d}/{t}.",
        "back": "↩ Back",
        "nothing_confirm": "No pages waiting for confirmation.",
        "pick_confirm": "Tick the pages you reviewed and accept (space to tick):",
        "your_name": "Your name (recorded in the confirmation):",
        "confirmed_n": "{n} pages confirmed.",
        "p_live": "📝 Open the portal (docs, review, C4, code graph, wikis — editable)", "p_build": "📦 Export the portal for deployment (read-only, CI / hosting)", "p_up": "🐳 Serve the export with Docker", "p_open": "Open in browser", "p_down": "Stop",
        "m_wikis": "📚 Wikis (OpenWiki)", "w_title": "Wikis per repo", "w_pages": "{n} pages", "w_none": "no wiki", "w_stale": "out of date",
        "w_pick": "Which repos should I generate / update?", "w_engine": "Who writes the wiki?", "w_open": "🌐 See them in the portal",
        "w_gen": "✨ Generate / update wikis", "w_eng_openwiki": "OpenWiki (saved provider key)",
        "w_eng_claude": "Claude Code (headless, with the OpenWiki MCP tools)", "w_eng_codex": "Codex (headless, with the OpenWiki MCP tools)",
        "w_no_engine": "OpenWiki cannot run headless yet. Save a provider key once with `openwiki auth configure openai` (or anthropic, gemini, openrouter), or install Claude Code / Codex.",
        "w_done": "Wiki ready: {repo}", "w_fail": "The {repo} wiki failed — the reason is on the ⚠ line above",
        "w_off": "no wiki (not chosen)", "w_need_brief": "first: its repo-brief (INSTRUCTIONS.md)",
        "w_choose": "🎯 Choose which repos get a wiki", "w_choose_first": "choose the repos first",
        "w_choose_q": "Which repos get a wiki? Each one is a full agent run: pick the services with logic, not libraries or CI repos",
        "w_none_chosen": "No repo has a wiki yet: choose which ones first (🎯).", "w_skipped": "Not started: {repos}", "w_unit_q": "How do you want to generate the {repo} wiki?",
        "w_none_ready": "None of the chosen repos is ready for a wiki ({repos}): each needs its repo-brief (INSTRUCTIONS.md) first. Run it from the plan.",
        "w_here": "✨ Right here (no agent session, {engine})", "w_agent": "🤖 Interactive agent session",
        "port": "Port:",
        "r_detect": "Detect repos in this folder", "r_add": "Add repo by URL", "r_sync": "Sync (clone / pull)",
        "r_remove": "Remove repo from project",
        "ci_forge": "Where do the repos live?",
        "ci_done": "Pipeline installed. Required variables: tutorial (docs/guides/tutorial.md §8).",
        "error": "Something failed:",
        "install_here": "You are inside “{kit}”. Install Camarón into the project folder “{parent}”?",
        "installed_here": "Installed in {parent}. Open Camarón from there (camaron.command / camaron.cmd).",
        "no_tty": "Camarón needs an interactive terminal. Use the commands: {cli} help",
        "unit_wizard": "The wizard does this unit itself.",
        "nav_select": "↑↓ move · Enter choose · Esc back",
        "nav_check": "↑↓ move · Space tick/untick · a all/none · Enter confirm · Esc back",
        "nav_text": "(Enter accept · Esc back)",
        "nav_confirm": "(y/n · Esc back)",
        "repos_title": "Project repos",
        "repos_none": "(none yet)",
        "r_continue": "✔ Continue with these repos",
        "r_pick": "Choose among the repos in this folder",
        "r_need": "add at least one repo",
        "prereq_continue": "✔ Continue",
        "prereq_retry": "↻ Check again",
        "prereq_blocked": "required prerequisites missing",
        "go_menu": "🦐 Go to the main menu",
        "setup_again": "↻ Run setup again",
        "exit_q": "Exit Camarón?",
        "pick_remove": "Tick the repos to remove:",
        "k_menu": "🔑 GitLab / GitHub tokens",
        "k_title": "Saved tokens",
        "k_none": "No tokens saved.",
        "k_add": "Add / update a token",
        "k_del": "Delete a token",
        "k_test": "Test tokens",
        "k_host": "Server (e.g. gitlab.com, github.com or gitlab.yourcompany.com):",
        "k_kind": "What is it?",
        "k_token": "Token (hidden while typing):",
        "k_scopes": "GitLab: personal token with 'read_api' + 'read_repository' (and 'write_repository' if Camarones should push). GitHub: fine-grained token with 'Contents: read' (and 'Metadata').",
        "k_privacy": "🔒 Stored in the OS keychain ({where}). Never written to the project or git config, never passed to Claude/Codex: only Camarones uses it to clone/update repos and list projects.",
        "k_ok": "✔ Valid token: signed in as {user}",
        "k_bad": "✖ The server rejected the token: {err}",
        "k_save_anyway": "Save it anyway?",
        "k_saved": "✔ Token saved for {host}",
        "k_pick_del": "Which one?",
        "r_remote": "Add from GitLab / GitHub (with token)",
        "r_scope": "GitLab group or GitHub organization (empty = every repo you can access):",
        "r_listing": "Looking for projects…",
        "r_pick_remote": "Tick the repos to add:",
        "r_none_remote": "No projects found with that token/group.",
        "r_which_host": "Which server?",
        "r_new_host": "➕ Another server / new token",
        "s_missing": "⚠ Could not clone: {repos}. Usually a permissions issue: add a token.",
        "s_token_retry": "🔑 Add a GitLab/GitHub token and retry",
        "a_menu": "🏗 Quick architecture diagram",
        "a_title": "First look at the architecture (static scan, no AI)",
        "a_question": "Does it look right? Shall I save it?",
        "a_save": "✔ Looks right, save it",
        "a_open": "🌐 Open it interactive in the browser",
        "a_ai": "✨ Save it and improve it with AI now",
        "a_again": "↻ Scan again",
        "a_skip": "✖ Don't save it, continue without it",
        "a_overwrite": "docs/architecture already has a C4 model. Replace it with this draft?",
        "a_saved": "✔ Saved as a draft in docs/architecture (the plan will refine it)",
        "a_invalid": "⚠ LikeC4 found errors in the draft; save it and the AI will fix it.",
        "a_users": "used by",
        "a_done": "The quick diagram is already done (saved {when}). What do you want to do?",
        "a_view": "🌐 View it in the portal (C4 tab)",
        "a_redo": "↻ Redo it (scan the repos again)",
        "a_keep": "✔ Keep it as it is",
        "sk_menu": "🧰 Stack & tools of each repo",
        "sk_intro": "I looked at each repo without AI: its stack and the tools you already use (Backstage, Sonar, component library, linters, contracts, CI…). The AI reads this first and refines it. If a stack is wrong, fix it here.",
        "sk_repo": "Repo", "sk_stack": "Stack", "sk_tools": "Tools found",
        "sk_detected": "detected",
        "sk_none": "No repos downloaded yet: I will scan them once they are (menu → Stack & tools).",
        "sk_question": "Is this right?",
        "sk_ok": "✔ Looks right, continue",
        "sk_fix": "✏ Fix a repo's stack",
        "sk_view": "🌐 View the page in the portal",
        "sk_pick": "Which repo?",
        "sk_fix_q": "Stack of {repo} (empty = the detected one):",
        "sk_done": "✔ Noted. I know what's in your toolbox now — no more fishing in the dark 🦐",
        "up_found": "A newer kit is available: v{new} (this project uses v{cur}).\nFound at: {where}",
        "up_q": "Upgrade now? (your config, the plan and all documentation are kept)",
        "up_done": "✔ Upgraded to v{new}. Restarting…",
        "fr_resumed": "Resuming the setup where you left it.",
        "m_resume": "▶ Continue “{u}” (left half done)",
        "m_review": "✅ Review & verify pages",
        "m_tutorial": "📖 Tutorial: what is each tool?",
        "m_uninstall": "🧹 Undo everything (remove this project's documentation)",
        "u_global": "Also clean your user-level files? (~/.camarones, saved tokens, wizard settings — shared by all your projects)",
        "u_preview": "This is what will be removed",
        "u_keep": "Not touched",
        "u_confirm": "Type the project name ({name}) to confirm:",
        "u_cancel": "Cancelled: nothing was removed.",
        "u_done": "✔ Done: {ws} holds just its repos again, exactly as they were.",
        "u_backup": "Backup of cam-docs: {path}",
        "d_doing": "In progress", "d_last": "last checkpoint", "d_fb": "your corrections pending",
        "k_doing": "Doing", "k_todo": "To do", "k_blocked": "Blocked", "k_done": "Done", "k_ready": "← ready",
        "res_q": "“{u}” was left half done. How shall I continue?",
        "res_new": "▶ New session resuming from the last checkpoint (recommended)",
        "res_cont": "💬 Reopen the last {agent} conversation",
        "res_done": "✔ It is finished: mark it done",
        "res_restart": "↺ Start this unit from scratch",
        "still_doing": "The unit is still half done. What was written is saved: next time choose “▶ Continue” and the AI resumes from the last checkpoint.",
        "saved_ckpt": "💾 Progress saved (local commit in the project folder, no push).",
        "rv_title": "✅ Review & verify",
        "rv_intro": "The AI writes drafts; you decide what is true. I'll show you the pages one by one (most important first):\n\n"
                    "  ✔ [bold]Looks right[/] → the page becomes [green]confirmed[/]: AIs use it as the source of truth and don't rewrite it "
                    "silently; the portal marks it verified. If someone changes it later it goes back to ⚠️ re-confirm.\n"
                    "  ✏️  [bold]Something's wrong[/] → write what's wrong (in your own words). It is saved to docs/.work/review-feedback.md "
                    "and the unit “Apply your corrections” shows up in “Next step” so the AI fixes it.\n"
                    "  ⏭ [bold]Skip[/] → leave it for another day.",
        "rv_none": "Nothing waiting for review 🎉",
        "rv_count": "{n} pages to review · {r} changed since they were confirmed",
        "rv_start": "▶ Start",
        "rv_head": "Page {i} of {n}",
        "rv_draft": "✨ AI draft", "rv_reconf": "⚠️ changed since it was confirmed",
        "rv_q": "What do you think of this page?",
        "rv_confirm": "✔ Looks right → confirm",
        "rv_change": "✏️  Something's wrong → request changes",
        "rv_full": "📖 Read it all",
        "rv_es": "🇪🇸 Show the Spanish translation", "rv_en": "🇬🇧 Show the original (English)",
        "rv_skip": "⏭ Skip",
        "rv_stop": "⏹ Finish reviewing",
        "rv_what": "What's wrong or missing? (the AI will fix it)",
        "rv_more": "… {n} more lines → “📖 Read it all”",
        "rv_showing_es": "Showing the Spanish translation (confirming applies to the original page).",
        "rv_sum": "Review: ✔ {c} confirmed · ✏️ {f} with changes requested · ⏭ {s} skipped",
        "rv_fix_now": "✨ Apply your corrections now with AI",
        "rv_later": "Later (it shows up in “Next step”)",
        "st_title": "🔎 Documentation status",
        "st_legend": "✅ confirmed by a person · ✨ AI draft · ⚠️ confirmed but changed afterwards · "
                     "orphan = cites code that no longer exists · translation = Spanish missing or behind",
        "st_problems": "What needs doing",
        "st_ok": "✔ All good: nothing to fix.",
        "st_err": "{n} format/link errors (check)",
        "st_orph": "{n} pages cite code that no longer exists",
        "st_reconf": "{n} confirmed pages changed: review them",
        "st_draft": "{n} drafts not reviewed",
        "st_i18n": "{n} translations missing or outdated",
        "st_fb": "{n} of your corrections not applied yet",
        "st_changes": "{n} repos with code changes not documented yet",
        "st_fix": "✨ Fix the problems with AI (errors, orphans, translations)",
        "st_review": "✅ Review pages ({n})",
        "st_apply": "✨ Apply your corrections ({n})",
        "st_update": "🔄 Document the code changes ({n} repos)",
        "st_list": "📄 Show every page",
        "p_local": "🐍 Serve the export without Docker",
        "p_docker_na": "Docker is not available ({why}). Serve it without Docker?",
        "p_running": "Portal running: {url}",
        "p_docker_fail": "Docker could not start it. Serve it without Docker meanwhile?",
        "tu_title": "📖 Tutorial", "tu_next": "▶ Next", "tu_prev": "◀ Previous", "tu_index": "📑 Contents",
        "tu_done": "✔ Got it, back to the menu", "tu_offer": "📖 See the tutorial (2 minutes): what each tool is",
        "facts": [
            "🦐 Did you know? A shrimp's heart is in its head.",
            "🦐 Did you know? Mantis shrimp have 12–16 kinds of photoreceptors; you have 3.",
            "🦐 Did you know? A mantis shrimp strikes so fast the water boils (cavitation).",
            "🦐 Did you know? Pistol shrimp snap their claw with a bang of over 200 decibels.",
            "🦐 Did you know? Cooked shrimp turn pink because heat releases astaxanthin from their proteins.",
            "🦐 Did you know? Cleaner shrimp run 'cleaning stations' where fish queue to get groomed.",
            "🦐 Did you know? Shrimp escape by flicking their abdomen and swimming backwards.",
            "🦐 Did you know? Antarctic krill are among the species with the largest biomass on Earth.",
            "🦐 Did you know? The mantis shrimp is neither a shrimp nor a mantis: it's a stomatopod.",
            "🦐 Did you know? Some shrimp are born male and become female as they age.",
            "🦐 Did you know? Hermit crabs line up by size to swap shells.",
            "🦐 The sleeping shrimp gets carried away by the current… that's why progress is saved.",
            "🦐 If this is slow, blame npm downloading half the internet, not the shrimp.",
            "🦐 Peeling repos gently, not a single commit harmed.",
            "🦐 A good C4 model is like a good broth: it takes patience.",
        ],
        "elapsed": "elapsed",
        "t_title": "Tools",
        "t_required": "required", "t_optional": "optional", "t_kit": "Camarones",
        "t_installed": "installed", "t_missing": "missing",
        "t_all": "✔ Install everything recommended (recommended)",
        "t_pick": "Choose what to install",
        "t_none": "Continue without installing anything else",
        "t_pick_q": "Tick what to install / enable:",
        "t_need_req": "git or Node.js missing: they are required",
        "t_installing": "Installing missing system tools",
        "agent_one_ok": "optional — {other} is enough",
        "agent_none": "no agent: you can copy prompts, but install Claude Code or Codex for the sessions",
        "java_sdkman": "Java is not active in this shell but SDKMAN is installed: using ~/.sdkman/candidates/java/current",
    },
}


class W:
    def __init__(self):
        self.prefs = load_json(PREFS, {})
        self.lang = self.prefs.get("lang") or ("es" if os.environ.get("LANG", "es").startswith("es") or IS_WIN else "en")

    def t(self, key: str, **kw) -> str:
        v = T[self.lang][key]
        return v.format(**kw) if kw and isinstance(v, str) else v

    # ---------- prompts: Esc = back everywhere, navigation help under every list ----------
    @staticmethod
    def _ask(q):
        kb = KeyBindings()

        @kb.add("escape", eager=True)
        def _(event):
            event.app.exit(result=BACK)

        q.application.key_bindings = merge_key_bindings([q.application.key_bindings, kb])
        try:
            return q.unsafe_ask()
        except KeyboardInterrupt:
            return BACK

    def help_rows(self, key: str) -> list:
        return [Separator(" "), Separator(f"  {self.t(key)}")]

    def sel(self, msg: str, choices: list, back: bool = True, default=None):
        """Single choice. Returns the value, or None when the user goes back (Esc / ↩ Volver / Ctrl+C)."""
        ch = list(choices) + ([Choice(self.t("back"), BACK)] if back else []) + self.help_rows("nav_select")
        r = self._ask(questionary.select(msg, choices=ch, style=STYLE, default=default, instruction=" "))
        return None if r in (None, BACK) else r

    def chk(self, msg: str, choices: list):
        """Multiple choice. Returns the list of values (possibly empty), or None when the user goes back."""
        if not any(isinstance(c, Choice) and not c.disabled for c in choices):
            return None     # questionary crashes (no pointed_at) when nothing is selectable
        r = self._ask(questionary.checkbox(msg, choices=list(choices) + self.help_rows("nav_check"), style=STYLE,
                                           instruction=" "))
        return None if r in (None, BACK) else r

    def txt(self, msg: str, default: str = ""):
        r = self._ask(questionary.text(msg, default=default, style=STYLE, instruction=self.t("nav_text")))
        return None if r in (None, BACK) else r

    def yes(self, msg: str, default: bool = True):
        r = self._ask(questionary.confirm(msg, default=default, style=STYLE, instruction=self.t("nav_confirm")))
        return None if r in (None, BACK) else r

    def pause(self) -> None:
        questionary.press_any_key_to_continue("↩").ask()

    # ---------- chrome ----------
    def banner(self, big: bool | None = None) -> None:
        console.clear()
        console.print(CAMARON)
        title = Text("  C A M A R Ó N", style=f"bold {ORANGE}")
        title.append(f"   v{VERSIONS['kit']}", style="grey50")
        console.print(title)
        console.print(Text(f"  🦐 {self.t('tagline')}", style="grey62"))
        console.print()
        if getattr(self, "step_hdr", None):
            console.print(self.step_hdr)

    def say(self, msg, style: str = "") -> None:
        console.print(msg, style=style)

    def busy(self, fn, *a, total: int | None = None, **kw):
        """Run fn in a thread and show: spinner + what it is doing now, progress bar, recent steps and shrimp facts."""
        st = {"cur": random.choice(self.t("busy")), "done": 0, "lines": []}

        def log(msg: str) -> None:
            m = str(msg).strip()
            if not m:
                return
            st["lines"].append(m)
            if m.startswith("✔"):
                st["done"] += 1
            else:
                st["cur"] = m

        box: dict = {}

        def work():
            try:
                box["v"] = fn(*a, log=log, **kw)
            except BaseException as e:  # noqa: BLE001 — re-raised in the UI thread
                box["e"] = e

        facts = list(self.t("facts"))
        random.shuffle(facts)
        frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        t0 = time.time()

        def view():
            el = time.time() - t0
            rows = [Text.from_markup(f"[bold {ORANGE}]{frames[int(el * 10) % 10]}[/] {st['cur']}")]
            if total:
                done = min(st["done"], total)
                bar = Progress(BarColumn(bar_width=40, complete_style=ORANGE, finished_style="green"),
                               TextColumn("{task.completed}/{task.total}"), TextColumn(f"· {int(el)}s {self.t('elapsed')}"))
                bar.add_task("", total=total, completed=done)
                rows.append(bar)
            else:
                rows.append(Text(f"{int(el)}s {self.t('elapsed')}", style="grey50"))
            for l in st["lines"][-6:]:
                rows.append(Text("  " + l, style="green" if l.startswith("✔") else ("yellow" if l.startswith("⚠") else "grey62")))
            rows.append(Text(""))
            rows.append(Panel(facts[int(el // 7) % len(facts)], border_style="#ffb38a"))
            return Group(*rows)

        th = threading.Thread(target=work, daemon=True)
        th.start()
        with Live(view(), console=console, refresh_per_second=10, transient=True) as live:
            while th.is_alive():
                live.update(view())
                time.sleep(0.1)
        for l in st["lines"]:
            if l.startswith(("✔", "⚠")):
                console.print("  " + l, style="green" if l.startswith("✔") else "yellow")
        if "e" in box:
            raise box["e"]
        return box.get("v")

    def safe(self, fn, *a, **kw):
        try:
            return fn(*a, **kw)
        except Exception as e:  # noqa: BLE001 — the wizard must survive any tool failure
            console.print(Panel(str(e), title=self.t("error"), border_style="red"))
            self.pause()                    # the menu redraw clears the screen: without this the error is never seen
            return None

    def dashboard(self) -> None:
        ws = docs.workspace()
        data = plan.load()
        d, t = plan.progress(data)
        rows = docs.collect() if (ROOT / "docs").exists() else []
        s = docs.summary(rows)
        tbl = Table.grid(padding=(0, 2))
        tbl.add_row("[bold]Proyecto[/]" if self.lang == "es" else "[bold]Project[/]", ws["project"]["name"])
        tbl.add_row("Repos", ", ".join(docs.repo_names()) or "—")
        bar = Progress(TextColumn("{task.description}"), BarColumn(bar_width=28, complete_style=ORANGE),
                       TextColumn("{task.completed}/{task.total}"))
        bar.add_task("Plan", total=max(t, 1), completed=d)
        tbl.add_row("Plan", bar)
        tbl.add_row("Docs", f"✅ {s['confirmed']}  ✨ {s['draft']}  ⚠️ {s['needs-reconfirm']}  "
                            f"{'huérfanas' if self.lang == 'es' else 'orphans'} {s['orphans']}")
        doing = [u for u in data["units"] if u["status"] == "doing"]
        for u in doing[:2]:
            last = plan.last_note(u["id"])
            tbl.add_row(f"[bold]▶ {self.t('d_doing')}[/]", f"[{ORANGE}]{u['id']}[/]" +
                        (f"  [grey62]{self.t('d_last')}: {last[:90]}[/]" if last else ""))
        fb = len(docs.pending_feedback())
        if fb:
            tbl.add_row("✏️", f"{fb} {self.t('d_fb')}")
        nxt = [u for u in plan.available(data) if u["status"] != "doing"]
        if nxt:
            tbl.add_row("→", f"[{ORANGE}]{nxt[0]['id']}[/] — {nxt[0]['title']}")
        console.print(Panel(tbl, border_style=ORANGE))

    # ---------- main loop ----------
    def run(self) -> None:
        if not sys.stdin.isatty():
            print(self.t("no_tty", cli=cli_cmd()))
            return
        console.set_alt_screen(True)          # full-screen app: no scrollback while the wizard is open
        try:
            self._run()
        finally:
            console.set_alt_screen(False)
            console.print(f"[bold {ORANGE}]🦐 {self.t('bye')}[/]")

    def _run(self) -> None:
        self.banner()
        from . import migrate
        if migrate.needed() and self.yes(self.t("migrate_ask", cam=CAM_DIR), default=True):
            console.set_alt_screen(False)
            if migrate.main() == 0:                          # module globals point at the old root: restart on the new one
                os.environ["CAMARONES_ROOT"] = str(ROOT / CAM_DIR)
                self.pause()
                os.execv(sys.executable, [sys.executable, str(Path(__file__).resolve().parent.parent / "camarones.py")])
            console.set_alt_screen(True)
            self.banner()
        state = load_json(FIRSTRUN, {})
        legacy_done = plan.PLAN.exists() and WS_FILE.exists() and not state   # installs from before v2.4
        if not state.get("done") and not legacy_done:
            if not self.first_run(resume_step(state)):
                return
        else:
            time.sleep(0.8)
        while True:
            self.banner()
            self.dashboard()
            doing = [u for u in plan.load()["units"] if u["status"] == "doing" and u["runner"] == "agent"]
            n_rev = len(docs.review_queue()) if (ROOT / "docs").exists() else 0
            choices = [Choice(self.t("m_resume", u=doing[0]["id"]), "resume")] if doing else []
            choices += [
                Choice(self.t("m_next"), "next"), Choice(self.t("m_plan"), "plan"), Choice(self.t("m_redo"), "redo"),
                Choice(self.t("m_review") + (f"  ({n_rev})" if n_rev else ""), "review"),
                Choice(self.t("m_portal"), "portal"), Choice(self.t("m_wikis"), "wikis"), Choice(self.t("m_status"), "status"), Choice(self.t("m_update"), "update"),
                Choice(self.t("a_menu"), "arch"), Choice(self.t("sk_menu"), "stack"), Choice(self.t("m_repos"), "repos"), Choice(self.t("k_menu"), "creds"),
                Choice(self.t("m_setup"), "setup"), Choice(self.t("m_ci"), "ci")]
            if self.extra_ready():
                choices.append(Choice(self.t("m_extra"), "extra"))
            choices += [
                Choice(self.t("m_tutorial"), "tutorial"), Choice(self.t("m_uninstall"), "uninstall"),
                Choice(self.t("m_model"), "model"), Choice(self.t("m_lang"), "lang"), Choice(self.t("m_exit"), "exit")]
            choice = self.sel(self.t("menu"), back=False, choices=choices)
            if choice == "resume":
                self.banner()
                self.safe(self.run_unit, doing[0])
                continue
            if choice is None:                      # Esc on the main menu: ask before leaving
                if self.yes(self.t("exit_q"), default=False):
                    choice = "exit"
                else:
                    continue
            if choice == "exit":
                return
            self.banner()
            if self.safe(getattr(self, f"do_{choice}")) == "gone":   # uninstalled: this project no longer exists
                return

    # ---------- first run: a step machine, Esc / ↩ goes one step back ----------
    def first_run(self, start: int = 0) -> bool:
        ws = docs.workspace()
        steps = [("Workspace", self.fr_name), ("Repos", self.fr_repos), (self.t("t_title"), self.fr_tools),
                 ("Setup", self.fr_setup), ("Stack", self.fr_stack), ("C4", self.fr_arch), ("🦐", self.fr_intro)]
        i = min(max(start, 0), len(steps) - 1)
        if i:
            self.resumed = True
        while i < len(steps):
            save_json(FIRSTRUN, {"step": i, "name": STEPS[i], "done": False})
            crumbs = "  ".join((f"[bold {ORANGE}]● {n}[/]" if k == i else (f"[green]✔ {n}[/]" if k < i else f"[grey50]○ {n}[/]"))
                               for k, (n, _) in enumerate(steps))
            self.step_hdr = f"[bold]{self.t('step', n=i + 1, t=len(steps))}[/]   {crumbs}\n"
            self.banner()
            if i == 0:
                self.say(Panel(self.t("welcome"), border_style=ORANGE))
            elif getattr(self, "resumed", False):
                self.say(f"[grey62]↻ {self.t('fr_resumed')}[/]")
                self.resumed = False
            r = steps[i][1](ws)
            if r == BACK:
                if i == 0:
                    if self.yes(self.t("exit_q"), default=False):
                        self.step_hdr = None
                        return False
                    continue
                i -= 1
            else:
                i += 1
        self.step_hdr = None
        save_json(FIRSTRUN, {"step": len(steps), "done": True})
        env.checkpoint_commit("first setup")
        return True

    def fr_name(self, ws: dict):
        name = self.txt(self.t("project_name"), default=ws["project"].get("name") or WORKSPACE.name)
        if name is None:
            return BACK
        ws["project"]["name"] = name.strip() or WORKSPACE.name
        ws["project"]["id"] = "".join(c if c.isalnum() else "-" for c in ws["project"]["name"].lower()).strip("-")
        ws["project"].setdefault("canonical_language", "en")
        ws["project"]["translations"] = ws["project"].get("translations") or ["es"]
        docs.save_workspace(ws)

    def show_repos(self, ws: dict) -> None:
        tbl = Table(title=self.t("repos_title"), title_justify="left", border_style="grey42", show_header=False)
        for r in ws["repos"]:
            tbl.add_row(f"[{ORANGE}]{r['name']}[/]", r.get("kind", ""), r.get("branch", ""), r.get("url") or "(local)")
        console.print(tbl if ws["repos"] else f"  {self.t('repos_none')}")

    def fr_repos(self, ws: dict):
        found = docs.detect_repos()
        if not ws["repos"] and found:          # first visit: preselect what is already in the folder, shown explicitly
            ws["repos"] = list(found)
            docs.save_workspace(ws)
        while True:
            self.show_repos(ws)
            choices = [Choice(self.t("r_continue"), "go", disabled=None if ws["repos"] else self.t("r_need"))]
            if found:
                choices.append(Choice(self.t("r_pick"), "pick"))
            choices.append(Choice(self.t("r_remote"), "remote"))
            choices.append(Choice(self.t("r_add"), "add"))
            if ws["repos"]:
                choices.append(Choice(self.t("r_remove"), "remove"))
            c = self.sel(self.t("menu"), choices, default="go" if ws["repos"] else "add")
            if c is None:
                return BACK
            if c == "go":
                docs.save_workspace(ws)
                return None
            if c == "pick":
                current = {r["name"] for r in ws["repos"]}
                picked = self.chk(self.t("found_repos"), [
                    Choice(f"{r['name']}  [{r['kind']}]  {r['url'] or '(local)'}", r["name"], checked=r["name"] in current)
                    for r in found])
                if picked is not None:
                    local = {r["name"] for r in found}
                    ws["repos"] = [r for r in ws["repos"] if r["name"] not in local] + [r for r in found if r["name"] in picked]
            elif c == "add":
                self.add_url(ws)
            elif c == "remote":
                self.add_remote(ws)
            elif c == "remove":
                gone = self.chk(self.t("pick_remove"), [Choice(r["name"], r["name"]) for r in ws["repos"]])
                if gone:
                    ws["repos"] = [r for r in ws["repos"] if r["name"] not in gone]
            docs.save_workspace(ws)
            self.banner()

    def add_url(self, ws: dict) -> bool:
        url = self.txt(self.t("add_url"))
        if not url:
            return False
        default = url.rstrip("/").split("/")[-1].removesuffix(".git")
        name = self.txt(self.t("repo_name"), default=default)
        if name is None:
            return False
        branch = self.txt(self.t("branch"), default="main")
        if branch is None:
            return False
        ws["repos"].append({"name": name or default, "url": url, "branch": branch or "main", "kind": "service"})
        docs.save_workspace(ws)
        return True

    # ---------- tools: everything in one table, install all (recommended) or pick ----------
    def tool_rows(self) -> list[dict]:
        pre = env.prerequisites()
        have_agent = any(pre[a]["ok"] for a in ("claude", "codex"))
        rows = []
        for k, v in pre.items():
            kind = "t_required" if v["need"] else "t_optional"
            rec = v["need"] or k in ("docker", "java") or (k == "claude" and not have_agent)
            rows.append({"id": k, "label": v["hint"], "ok": v["ok"], "kind": kind, "rec": rec, "sys": True,
                         "found": v.get("found", ""), "note": v.get("note", "")})
        chosen = env.components()
        for k, label in {**env.KIT_TOOLS, **env.EXTRAS}.items():
            installed = env.tool_ok(k) if k in env.KIT_TOOLS else (k in chosen)
            rows.append({"id": k, "label": label, "ok": installed, "kind": "t_kit", "rec": True, "sys": False,
                         "found": env.VERSIONS.get(k, "") if installed and k in env.KIT_TOOLS else "", "note": ""})
        return rows

    def show_tools(self, rows: list[dict]) -> None:
        tbl = Table(border_style="grey42", title=self.t("t_title"), title_justify="left")
        for c in ("", "", "", ""):
            tbl.add_column(c)
        have_agent = any(r["ok"] for r in rows if r["id"] in ("claude", "codex"))
        for r in rows:
            if r["ok"]:
                st = f"[green]✔ {self.t('t_installed')}[/]"
            elif r["id"] in ("claude", "codex") and have_agent:
                st = f"[grey50]· {self.t('agent_one_ok', other='claude' if r['id'] == 'codex' else 'codex')}[/]"
            else:
                st = f"[{'red' if r['kind'] == 't_required' else 'yellow'}]✖ {self.t('t_missing')}[/]"
            tbl.add_row(f"[{ORANGE}]{r['id']}[/]", st, f"[grey62]{self.t(r['kind'])}[/]", r["label"] + (f"  [grey50]{r['found']}[/]" if r["found"] else ""))
            if r["note"]:
                tbl.add_row("", "", "", f"[grey50]{r['note']}[/]")
        console.print(tbl)

    def fr_tools(self, ws: dict):
        while True:
            rows = self.tool_rows()
            self.show_tools(rows)
            req_ok = all(r["ok"] for r in rows if r["kind"] == "t_required")
            c = self.sel(self.t("menu"), [Choice(self.t("t_all"), "all"), Choice(self.t("t_pick"), "pick"),
                                          Choice(self.t("t_none"), "none", disabled=None if req_ok else self.t("t_need_req"))],
                         default="all")
            if c is None:
                return BACK
            have_agent = any(r["ok"] for r in rows if r["id"] in ("claude", "codex"))
            if c == "all":
                sys_pick = [r["id"] for r in rows if r["sys"] and not r["ok"] and r["rec"]
                            and not (r["id"] in ("claude", "codex") and have_agent)]
                kit_pick = list(env.ALL_COMPONENTS)
            elif c == "pick":
                opts = []
                for r in rows:
                    if r["sys"] and r["ok"]:
                        continue
                    if r["sys"] and r["id"] in ("claude", "codex") and have_agent:
                        continue
                    opts.append(Choice(f"{r['id']:<9} {r['label']}", r["id"],
                                       checked=(r["kind"] == "t_required") or (not r["sys"] and (r["ok"] or r["rec"]))))
                picked = self.chk(self.t("t_pick_q"), opts)
                if picked is None:
                    self.banner()
                    continue
                sys_pick = [p for p in picked if p in env.prerequisites()]
                kit_pick = [p for p in picked if p in env.ALL_COMPONENTS]
            else:
                sys_pick, kit_pick = [], env.components()
            env.set_components(kit_pick)
            if sys_pick:
                self.say(f"[bold]{self.t('t_installing')}: {', '.join(sys_pick)}[/]")
                for k in sys_pick:
                    if not env.install_prereq(k, log=lambda m: self.say("  " + m, "grey62")):
                        self.say(self.t("manual", hint=env.prerequisites().get(k, {}).get("hint", k)), "yellow")
                from .common import ensure_path
                ensure_path()
            if all(v["ok"] for v in env.prerequisites().values() if v["need"]):
                return None
            self.say(self.t("reopen"), "yellow")
            self.pause()
            self.banner()

    def fr_setup(self, ws: dict):
        self.repo_pointer()
        self.say(f"[bold]{self.t('setup_run')}[/]")
        env.init_templates(ws["project"]["name"], log=lambda _: None)
        ok = self.safe(self.busy, env.setup, total=env.setup_steps())
        plan.sync()
        if ok:
            plan.set_status("setup", "done", "wizard first run")
            self.say(self.t("setup_ok"), f"bold {ORANGE}")
        while True:
            missing = [r["name"] for r in docs.workspace()["repos"] if r.get("url") and not (repo_dir(r["name"]) / ".git").exists()]
            if missing:
                self.say(self.t("s_missing", repos=", ".join(missing)), "yellow")
            choices = [Choice(self.t("prereq_continue"), "go", disabled=None if ok else "setup ✖")]
            if missing:
                choices.append(Choice(self.t("s_token_retry"), "token"))
            choices.append(Choice(self.t("setup_again"), "again"))
            c = self.sel(self.t("menu"), choices, default="token" if missing else ("go" if ok else "again"))
            if c is None:
                return BACK
            if c == "go":
                return None
            if c == "token":
                host = creds.host_of(next(r["url"] for r in docs.workspace()["repos"] if r["name"] == missing[0]))
                self.banner()
                self.add_token(host)
            self.banner()
            ok = self.safe(self.busy, env.setup, total=env.setup_steps())
            if ok:
                plan.set_status("setup", "done", "wizard")

    def fr_intro(self, ws: dict):
        while True:
            self.say(Panel(self.t("sessions_intro"), border_style=ORANGE))
            c = self.sel(self.t("menu"), [Choice(self.t("go_menu"), "go"), Choice(self.t("tu_offer"), "tutorial")])
            if c is None:
                return BACK
            if c == "go":
                return None
            self.do_tutorial()
            self.banner()

    def prereqs(self) -> bool:
        ok = True
        have_agent = [a for a in ("claude", "codex") if which(a)]
        for k, v in env.prerequisites().items():
            mark = "✔" if v["ok"] else ("✖" if v["need"] else "·")
            extra = v.get("found", "")
            if k in ("claude", "codex") and not v["ok"]:
                extra = self.t("agent_one_ok", other=have_agent[0]) if have_agent else self.t("agent_none")
            self.say(f"  {mark} {k:<7} {extra}", "green" if v["ok"] else ("red" if v["need"] else "grey50"))
            if v.get("note"):
                self.say(f"      {v['note']}", "grey62")
            if v["ok"] or (k in ("claude", "codex") and (which("claude") or which("codex"))):
                continue
            ans = self.yes(self.t("missing", what=v["hint"]), default=v["need"])
            if ans:
                if env.install_prereq(k, log=lambda m: self.say("  " + m, "grey62")):
                    if k in ("git", "node", "docker", "java"):
                        self.say(self.t("reopen"), "yellow")
                        ok = ok and not v["need"]
                else:
                    self.say(self.t("manual", hint=v["hint"]), "yellow")
                    ok = ok and not v["need"]
            elif v["need"]:
                ok = False
        return ok


    # ---------- tokens (GitLab / GitHub) ----------
    def show_creds(self) -> None:
        h = creds.hosts()
        if not h:
            self.say(self.t("k_none"), "grey62")
            return
        tbl = Table(title=self.t("k_title"), title_justify="left", border_style="grey42")
        for c in ("host", "kind", "user", "🔑"):
            tbl.add_column(c)
        for host, meta in h.items():
            tbl.add_row(f"[{ORANGE}]{host}[/]", meta.get("kind", ""), meta.get("user", ""), "✔" if creds.get(host) else "✖")
        console.print(tbl)

    def add_token(self, host: str | None = None) -> str | None:
        """Ask host/kind/token, verify against the API, store in the OS keychain. Returns the host or None."""
        repo_hosts = [creds.host_of(r.get("url", "")) for r in docs.workspace()["repos"]]
        default = host or next((x for x in repo_hosts if x and not creds.get(x)), None) or "gitlab.com"
        self.say(Panel(self.t("k_scopes") + "\n\n" + self.t("k_privacy", where=creds.backend_name()), border_style="grey50"))
        host = self.txt(self.t("k_host"), default=default)
        if not host:
            return None
        host = creds.host_of(host if "://" in host else f"https://{host.strip()}") or host.strip()
        kind = self.sel(self.t("k_kind"), [Choice("GitLab", "gitlab"), Choice("GitHub", "github")], default=creds.guess_kind(host))
        if not kind:
            return None
        token = self._ask(questionary.password(self.t("k_token"), style=STYLE, instruction=self.t("nav_text")))
        if token in (None, BACK) or not token.strip():
            return None
        token = token.strip()
        ok, info = self.busy(lambda log: (log("checking the token with the API…"), creds.verify(host, kind, token))[1])
        if ok:
            self.say(self.t("k_ok", user=info), "green")
        else:
            self.say(self.t("k_bad", err=info), "red")
            if not self.yes(self.t("k_save_anyway"), default=False):
                return None
        creds.save(host, kind, token, info if ok else "")
        self.say(self.t("k_saved", host=host), "green")
        return host

    def do_creds(self) -> None:
        while True:
            self.banner()
            self.show_creds()
            c = self.sel(self.t("k_menu"), [Choice(self.t("k_add"), "add"), Choice(self.t("k_test"), "test"),
                                            Choice(self.t("k_del"), "del", disabled=None if creds.hosts() else "—")])
            if not c:
                return
            if c == "add":
                self.add_token()
                self.pause()
            elif c == "test":
                for host, meta in creds.hosts().items():
                    tok = creds.get(host)
                    ok, info = creds.verify(host, meta.get("kind", "gitlab"), tok) if tok else (False, "no token")
                    self.say((self.t("k_ok", user=info) if ok else self.t("k_bad", err=info)) + f"  [{host}]",
                             "green" if ok else "red")
                self.pause()
            elif c == "del":
                h = self.sel(self.t("k_pick_del"), [Choice(x, x) for x in creds.hosts()])
                if h:
                    creds.delete(h)

    def add_remote(self, ws: dict) -> None:
        saved = [h for h in creds.hosts() if creds.get(h)]
        host = self.sel(self.t("r_which_host"), [Choice(h, h) for h in saved] + [Choice(self.t("r_new_host"), "__new__")],
                        default=saved[0] if saved else "__new__")
        if not host:
            return
        if host == "__new__":
            host = self.add_token()
            if not host:
                return
        kind = creds.hosts().get(host, {}).get("kind", creds.guess_kind(host))
        scope = self.txt(self.t("r_scope"))
        if scope is None:
            return
        projects = self.safe(self.busy, lambda log: (log(self.t("r_listing")),
                                                      creds.list_projects(host, kind, creds.get(host), scope.strip()))[1])
        if not projects:
            self.say(self.t("r_none_remote"), "yellow")
            self.pause()
            return
        have = {r["name"] for r in ws["repos"]}
        picked = self.chk(self.t("r_pick_remote"), [Choice(f"{p['path']}  [{p['branch']}]", p, checked=False)
                                                    for p in projects if p["name"] not in have])
        for p in picked or []:
            ws["repos"].append({"name": p["name"], "url": p["url"], "branch": p["branch"], "kind": "service"})
        docs.save_workspace(ws)

    # ---------- first look: quick architecture diagram ----------
    def show_arch(self, m: dict) -> None:
        project = docs.workspace()["project"]["name"]
        tree = Tree(f"[bold {ORANGE}]🏗 {project}[/]  [grey50]{self.t('a_title')}[/]")
        icon = {"service": "📦", "webapp": "🖥", "mobileApp": "📱", "library": "📚", "infra": "⚙"}
        out_edges: dict = {}
        for a, b, kind, label in m["edges"]:
            out_edges.setdefault(a, []).append((b, kind, label))
        dbname = lambda k: f"{m['dbs'][k]['label']}: {m['dbs'][k]['name']}" if k in m["dbs"] else k
        for n, r in m["repos"].items():
            node = tree.add(f"{icon.get(r['kind'], '📦')} [bold]{n}[/]  [grey62]{r['tech']}[/]")
            for b, kind, label in out_edges.get(n, []):
                arrow = "⇢" if kind == "async" else "→"
                tgt = dbname(b)
                node.add(f"[{'#6ec6ff' if kind == 'async' else ORANGE}]{arrow}[/] {tgt}  [grey62]{label}[/]")
            if n in m["caches"]:
                node.add("→ Redis cache")
        for k, d in m["dbs"].items():
            if len(d["users"]) > 1:
                tree.add(f"🗄 [yellow]{dbname(k)} — shared DB[/] [grey62]{self.t('a_users')}: {', '.join(sorted(d['users']))}[/]")
        for b in sorted(m["brokers"]):
            subs = [f"{b2} ({l2})" for a2, b2, _, l2 in m["edges"] if a2 == b]
            if subs:
                tree.add(f"📨 {b} → " + ", ".join(subs))
        console.print(tree)
        if m.get("valid") is False:
            self.say(self.t("a_invalid"), "yellow")

    def arch_flow(self) -> str:
        """Returns 'saved', 'skipped' or BACK."""
        page = docs.DOCS / "architecture" / "first-look.md"      # written when a draft is saved
        while page.exists():
            self.banner()
            when = time.strftime("%Y-%m-%d %H:%M", time.localtime(page.stat().st_mtime))
            c = self.sel(self.t("a_done", when=when), [Choice(self.t("a_view"), "view"), Choice(self.t("a_redo"), "redo"),
                                                         Choice(self.t("a_keep"), "keep")])
            if c is None:
                return BACK
            if c == "keep":
                return "saved"
            if c == "redo":
                break
            self.open_portal("#/c4")
        while True:
            self.banner()
            m = self.safe(self.busy, quickarch.draft, total=3)
            if not m:
                c = self.sel(self.t("menu"), [Choice(self.t("a_again"), "again"), Choice(self.t("a_skip"), "skip")])
                if c == "again":
                    continue
                return BACK if c is None else "skipped"
            while True:
                self.banner()
                self.show_arch(m)
                c = self.sel(self.t("a_question"), [Choice(self.t("a_save"), "save"),
                                                    Choice(self.t("a_open"), "open", disabled=None if m.get("html") else "LikeC4 ✖"),
                                                    Choice(self.t("a_ai"), "ai"), Choice(self.t("a_again"), "again"),
                                                    Choice(self.t("a_skip"), "skip")], default="save")
                if c is None:
                    return BACK
                if c == "open":
                    webbrowser.open(m["html"].as_uri())
                    continue
                if c == "again":
                    break
                if c == "skip":
                    return "skipped"
                exists = (docs.DOCS / "architecture" / "model.c4").exists()
                overwrite = False
                if exists:
                    overwrite = bool(self.yes(self.t("a_overwrite"), default=False))
                quickarch.save(m, overwrite=overwrite)
                self.say(self.t("a_saved"), "green")
                if c == "ai":
                    self.launch_agent(self.arch_prompt())
                else:
                    time.sleep(1.2)
                return "saved"

    def arch_prompt(self) -> str:
        cli = cli_cmd()
        talk = "Spanish" if self.lang == "es" else "English"
        arch = ws_rel("docs/architecture")
        # the agent runs in WORKSPACE: in the cam-docs layout a bare `docs/…` path would make it write a second,
        # unused model next to the repos while the portal keeps showing the unrefined draft
        layout = (f"\nLayout: you run in the workspace folder. Docs live in `{CAM_DIR}/` (its own git repo); the service repos "
                  f"are its siblings. Edit only the files under `{arch}/` — never create a `docs/` folder anywhere else.\n"
                  if CAM_LAYOUT else "")
        code = ("`graphify query` in the repos, " if "graphify" in env.components() else "")
        return f"""Camarones session — improve the first-look architecture draft.
{layout}
`{arch}/model.c4` + `views.c4` hold the architecture draft; it started from a static scan (no AI) that guessed repos,
datastores, brokers and HTTP calls from manifests, config and code. Read `{ws_rel('.camarones/CONVENTIONS.md')}` §4
(C4 rules) and the kinds/tags in `{arch}/spec.c4` first (do not edit spec.c4).
1. Verify every element and relation against the code ({code}OpenAPI/AsyncAPI files, config, client code).
   Fix technologies, names, directions and labels (endpoint / exchange / topic); remove false positives; add what is missing
   (external systems, identity provider, shared databases, frontends/apps). A relation is a runtime call or message —
   hosting/CI/deployment targets belong to the deployment unit, not here.
2. Keep `views.c4` in step with the model: `index` must show the actors, the system and every external system;
   `containers` everything inside the system. Remove view references to elements you deleted.
3. Keep everything `#ai-draft`. Run `{cli} arch-validate` after every edit until it prints ✓ Valid (it validates
   `{arch}/`, so a model written anywhere else is not checked). Update `{arch}/first-look.md` to match.
4. Show the user the result as a short tree (containers → relations) and ask whether it is right; apply their corrections.
   Tell them the portal's Architecture (C4) tab rebuilds from `{arch}/` (`{cli} up`).
Talk to the user in {talk}. Do not modify application code.
"""

    # ---------- stack + tooling radar (static, no AI) ----------
    def show_stack(self, result: dict) -> None:
        self.say(Panel(self.t("sk_intro"), border_style="grey42"))
        tbl = Table(border_style="grey42")
        for col in ("sk_repo", "sk_stack", "sk_tools"):
            tbl.add_column(self.t(col))
        for name, r in result.items():
            st = r["stack"] + (f"\n[grey50]{self.t('sk_detected')}: {r['detected_stack']}[/]"
                               if r["stack"] != r["detected_stack"] else "")
            tools = ", ".join(t["label"] for t in r["tools"]) or "—"
            tbl.add_row(f"[{ORANGE}]{name}[/]", st, f"[grey62]{tools}[/]")
        console.print(tbl)

    def stack_flow(self) -> str:
        """Returns 'done' or BACK."""
        scan = True
        while True:
            if scan:
                self.safe(self.busy, radar.run, total=1)
                scan = False
            result = load_json(radar.CACHE_FILE, {})
            self.banner()
            if not result:
                self.say(self.t("sk_none"), "yellow")
            else:
                self.show_stack(result)
            c = self.sel(self.t("sk_question"), [
                Choice(self.t("sk_ok"), "ok"), Choice(self.t("sk_fix"), "fix", disabled=None if result else "—"),
                Choice(self.t("sk_view"), "view", disabled=None if result else "—")], default="ok")
            if c is None:
                return BACK
            if c == "ok":
                if result:
                    self.say(self.t("sk_done"), f"bold {ORANGE}")
                    time.sleep(1.2)
                return "done"
            if c == "view":
                self.open_portal("#/docs/overview/tooling.md")
                continue
            repo = self.sel(self.t("sk_pick"), [Choice(f"{n}  ({r['stack']})", n) for n, r in result.items()])
            if repo is None:
                continue
            text = self.txt(self.t("sk_fix_q", repo=repo), default=result[repo]["stack"])
            if text is None:
                continue
            same = text.strip() in ("", result[repo]["detected_stack"])
            radar.set_stack(repo, None if same else text)
            scan = True

    def fr_stack(self, ws: dict):
        return BACK if self.stack_flow() == BACK else None

    def do_stack(self) -> None:
        self.stack_flow()

    def fr_arch(self, ws: dict):
        r = self.arch_flow()
        return BACK if r == BACK else None

    def do_arch(self) -> None:
        self.arch_flow()

    # ---------- menu actions ----------
    def do_next(self) -> None:
        plan.sync()
        ready = plan.available()
        if not ready:
            self.say(self.t("all_done"), f"bold {ORANGE}")
            self.pause()
            return
        choices = [Choice(f"{'▶ ' if u['status'] == 'doing' else ''}{u['id']} — {u['title']}", u) for u in ready[:8]]
        if any(u["runner"] == "agent" for u in ready) and (which("claude") or which("codex")):
            choices.append(Choice(self.t("autopilot"), "autopilot"))
        u = self.sel(self.t("ready_units"), choices)
        if u == "autopilot":
            self.do_autopilot()
        elif u:
            self.run_unit(u)

    def do_redo(self) -> None:
        data = plan.sync()
        done = sorted((u for u in data["units"] if u["status"] == "done"), key=lambda u: u["phase"])
        if not done:
            self.say(self.t("rd_none"), "yellow")
            self.pause()
            return
        u = self.sel(self.t("rd_pick"), [Choice(f"{u['id']} — {u['title']}", u) for u in done])
        if not u:
            return
        also = []
        if deps := plan.dependents(data, u["id"]):
            also = self.chk(self.t("rd_deps", u=u["id"]), [Choice(f"{d['id']} — {d['title']}", d["id"]) for d in deps])
            if also is None:
                return
        plan.redo(u["id"], also)
        self.checkpoint(f"redo {u['id']}")
        self.say(self.t("rd_ok", u=u["id"]), "green")
        if self.yes(self.t("rd_now"), default=True):
            self.run_unit(plan.get(plan.load(), u["id"]))

    def do_autopilot(self) -> None:
        self.say(self.t("autopilot_info"), "grey62")
        cmd = [sys.executable, str(Path(__file__).resolve().parent.parent / "camarones.py"), "autopilot", "--lang", self.lang]
        # the new window must work on THIS project, not whatever a walk up from WORKSPACE finds first
        os.environ["CAMARONES_ROOT"] = str(ROOT)
        if not IS_WIN:
            cmd = ["env", f"CAMARONES_ROOT={ROOT}", *cmd]      # a macOS/Linux terminal window does not inherit it
        if env.open_new_terminal(cmd, WORKSPACE):     # long-lived loop in its own window; the wizard stays usable
            self.say(self.t("autopilot_bg"), "green")
            self.pause()
            return
        console.set_alt_screen(False)
        try:
            subprocess.run(cmd, cwd=str(WORKSPACE))
        except KeyboardInterrupt:
            pass
        finally:
            console.set_alt_screen(True)
            self.banner()
        self.pause()

    def run_unit(self, u: dict) -> None:
        if u["runner"] == "wizard":
            self.say(self.t("unit_wizard"), "grey62")
            action = {"setup": self.do_setup, "portal": self.do_portal, "ci": self.do_ci, "confirm": self.do_review}[u["type"]]
            res = self.safe(action)
            if res is True or (u["type"] == "portal" and (CACHE / "site" / "index.html").exists()):
                plan.set_status(u["id"], "done", "wizard")
                self.checkpoint(u["id"])
            return
        if u["type"] == "repo-wiki" and (engines := env.wiki_engines()):
            c = self.sel(self.t("w_unit_q", repo=u["repo"]), [Choice(self.t("w_here", engine=engines[0]), "here"),
                                                              Choice(self.t("w_agent"), "agent")])
            if c is None:
                return
            if c == "here":
                ok = self.safe(self.busy, env.openwiki_generate, u["repo"], engine=self.wiki_engine() or engines[0])
                self.say(self.t("w_done", repo=u["repo"]) if ok else self.t("w_fail", repo=u["repo"]), "green" if ok else "yellow")
                return
        resume_agent = None
        if u["status"] == "doing":                      # interrupted session: offer how to pick it up again
            last = plan.last_note(u["id"])
            if last:
                self.say(f"[grey62]{self.t('d_last')}: {last}[/]")
            prev = self.prefs.get("last_agent")
            opts = [Choice(self.t("res_new"), "new")]
            if prev and which(prev):
                opts.append(Choice(self.t("res_cont", agent="Claude Code" if prev == "claude" else "Codex"), "continue"))
            opts += [Choice(self.t("res_done"), "done"), Choice(self.t("res_restart"), "restart")]
            c = self.sel(self.t("res_q", u=u["id"]), opts)
            if c is None:
                return
            if c == "done":
                plan.set_status(u["id"], "done", "marked done in the wizard")
                self.checkpoint(u["id"])
                return
            if c == "restart":
                f = plan.note_file(u["id"])
                if f.exists():
                    f.rename(f.with_suffix(".old.md"))
                plan.set_status(u["id"], "todo")
            if c == "continue":
                resume_agent = prev
        plan.set_status(u["id"], "doing")               # so a closed window still knows what was in progress
        prompt = plan.prompt(u["id"], lang=self.lang)
        res = self.launch_agent(prompt, resume_agent=resume_agent)
        if not res:
            return
        if res == "bg":               # own window: it updates plan.yaml itself, nothing to report here yet
            return
        u2 = plan.get(plan.load(), u["id"])
        self.checkpoint(u["id"] if u2["status"] == "done" else f"wip {u['id']}")
        if u2["status"] == "doing":
            self.say(self.t("still_doing"), "yellow")
        d, t = plan.progress()
        self.say(self.t("after", d=d, t=t), f"bold {ORANGE}")
        self.pause()

    def checkpoint(self, what: str) -> None:
        if env.checkpoint_commit(what):
            self.say(self.t("saved_ckpt"), "grey62")

    def launch_agent(self, prompt: str, resume_agent: str | None = None) -> bool | str:
        """Returns "bg" when the session was launched in its own window (the wizard stays usable), True when it
        ran to completion in this terminal (no terminal emulator was found), or False when nothing was launched.
        resume_agent reopens that agent's last conversation."""
        WORK.mkdir(parents=True, exist_ok=True)
        (WORK / "next-prompt.md").write_text(prompt, encoding="utf-8")
        if resume_agent:
            agent = resume_agent
        else:
            agents = [Choice("Claude Code", "claude")] if which("claude") else []
            agents += [Choice("Codex", "codex")] if which("codex") else []
            agents += [Choice(self.t("copy_prompt"), "copy")]
            agent = self.sel(self.t("which_agent"), agents, default=self.prefs.get("last_agent") if which(
                self.prefs.get("last_agent") or "-") else None)
        if not agent:
            return False
        if agent == "copy":
            self.say(self.t("copied") if copy_clipboard(prompt) else self.t("saved_prompt"), "green")
            console.print(Panel(prompt, border_style="grey50"))
            self.pause()
            return False
        self.prefs["last_agent"] = agent
        save_json(PREFS, self.prefs)
        self.say(self.t("launching", agent=agent), f"bold {ORANGE}")
        # multi-line args do not survive Windows .cmd shims: hand over a one-line pointer to the prompt file
        brief = ws_rel("docs/.work/next-prompt.md")
        short = f"Follow the instructions in {brief}" if self.lang == "en" else f"Sigue las instrucciones de {brief}"
        model = self.prefs.get("model", "sonnet")
        codex_model = self.prefs.get("codex_model", CODEX_MODEL_DEFAULT)
        model_args = ["--model", model] if agent == "claude" and model else (
            ["--model", codex_model] if agent == "codex" and codex_model else [])
        if resume_agent == "claude" and not claude_history(WORKSPACE):
            resume_agent = None                          # nothing to continue here: `--continue` would just error out
        if resume_agent == "claude":
            cmd = [which("claude"), *model_args, "--continue", short]
        elif resume_agent == "codex":
            cmd = [which("codex"), "resume", "--last"]
        else:
            cmd = [which(agent), *model_args, short]
        if env.open_new_terminal(cmd, WORKSPACE):   # own window, in the workspace: the agent sees every repo + cam-docs
            self.say(self.t("launched_bg"), "green")
            self.pause()
            return "bg"
        console.set_alt_screen(False)         # fallback: no terminal emulator found — block this one instead
        try:
            r = subprocess.run(cmd, cwd=str(WORKSPACE))
            if resume_agent and r.returncode != 0:          # nothing to resume (or old CLI): fresh session instead
                subprocess.run([which(agent), *model_args, short], cwd=str(WORKSPACE))
        finally:
            console.set_alt_screen(True)
            self.banner()
        return True

    def do_update(self) -> None:
        if self.launch_agent(plan.prompt("update", lang=self.lang)) is True:   # not "bg": that session checkpoints itself
            self.checkpoint("update")

    def do_plan(self) -> None:
        plan.sync()
        self.paged(self.board())

    def paged(self, renderable) -> None:
        """Anything taller than the screen goes through the pager (the alt screen has no scrollback)."""
        with console.capture() as cap:
            console.print(renderable)
        lines = cap.get().splitlines()
        if len(lines) < console.size.height - 4:
            console.print(renderable)
            self.pause()
            return
        if not IS_WIN:
            os.environ.setdefault("LESS", "-R")
            with console.pager(styles=True):
                console.print(renderable)
            return
        # Windows: rich's pager goes through pydoc + `more`, which re-encodes to the console code page and turns
        # every box-drawing character and emoji into \uXXXX escapes — page the captured lines here instead
        size = max(console.size.height - 3, 5)
        pages = -(-len(lines) // size)
        for n in range(pages):
            console.clear()
            for line in lines[n * size:(n + 1) * size]:
                console.print(Text.from_ansi(line), soft_wrap=True)
            more = f"-- {'más' if self.lang == 'es' else 'more'} ({n + 1}/{pages}) --"
            questionary.press_any_key_to_continue("↩" if n == pages - 1 else more).ask()

    def extra_ready(self) -> bool:
        """Whether any opt-in review (security-review, architecture-review) can be offered or is already in the plan."""
        status = {u["id"]: u["status"] for u in plan.load()["units"]}
        return any(uid in status or all(status.get(d) == "done" for d in deps) for uid, deps in EXTRA_REVIEWS.items())

    def do_extra(self) -> None:
        status = {u["id"]: u["status"] for u in plan.load()["units"]}
        opts = []
        for uid, deps in EXTRA_REVIEWS.items():
            added = uid in status
            ready = added or all(status.get(d) == "done" for d in deps)
            if not ready:
                continue
            title = plan.TYPES[uid][2]
            opts.append(Choice(title, uid, checked=added, disabled=self.t("extra_already") if added else None))
        picked = self.chk(self.t("extra_pick"), opts)
        if picked is None:
            return
        n = 0
        for uid in picked:
            if uid not in status:
                plan.add(uid, plan.TYPES[uid][2], uid, EXTRA_REVIEWS[uid])
                n += 1
        if n:
            self.say(self.t("extra_added", n=n), "green")
        self.pause()

    def board(self) -> Panel:
        """Kanban view of the plan: one column per status, so parallel work in other windows is easy to track."""
        data = plan.load()
        ready = {u["id"] for u in plan.available(data)}
        cols = [("doing", "▶", "k_doing"), ("todo", "·", "k_todo"), ("blocked", "✖", "k_blocked"), ("done", "✔", "k_done")]
        buckets: dict[str, list[str]] = {k: [] for k, _, _ in cols}
        for u in sorted(data["units"], key=lambda u: u["phase"]):
            st = u["status"]
            if st in ("dropped",):
                continue
            bucket = st if st in buckets else "done"      # dynamic/legacy statuses land with the finished work
            mark = f"  [grey62]{self.t('k_ready')}[/]" if u["id"] in ready and st == "todo" else ""
            mark += f"  [{ORANGE}]↻[/]" if u.get("redo") else ""
            note = f"\n  [grey50]{u['notes']}[/]" if u.get("notes") and st == "blocked" else ""
            buckets[bucket].append(f"[{ORANGE}]{u['id']}[/]{mark}\n  [grey62]{u['title']}[/]{note}")
        tbl = Table(box=box.SIMPLE_HEAVY, expand=True, pad_edge=False)
        for key, icon, label in cols:
            tbl.add_column(f"{icon} {self.t(label)} ({len(buckets[key])})", ratio=1)
        height = max((len(v) for v in buckets.values()), default=0)
        for i in range(height):
            tbl.add_row(*[buckets[k][i] if i < len(buckets[k]) else "" for k, _, _ in cols])
        d, t = plan.progress(data)
        return Panel(tbl, title=f"📋 Plan — {d}/{t}", border_style=ORANGE)

    # ---------- verify: status that tells you what to do, with one-click fixes ----------
    def do_status(self) -> None:
        while True:
            self.banner()
            rows = docs.collect()
            s = docs.summary(rows)
            errors, _ = docs.check()
            fb = docs.pending_feedback()
            ch = {k: v for k, v in docs.changes().items() if v.get("status") in ("changed", "history-rewritten")}
            tbl = Table.grid(padding=(0, 2))
            tbl.add_row("✅", str(s["confirmed"]), "✨", str(s["draft"]), "⚠️", str(s["needs-reconfirm"]),
                        "🧩", f"{s['orphans']} {'huérfanas' if self.lang == 'es' else 'orphans'}",
                        "🌍", f"{s['untranslated']}")
            console.print(Panel(Group(tbl, Text(""), Text(self.t("st_legend"), style="grey62")),
                                title=self.t("st_title"), title_align="left", border_style=ORANGE))
            todo = []
            if errors:
                todo.append(("red", self.t("st_err", n=len(errors))))
            if s["orphans"]:
                todo.append(("yellow", self.t("st_orph", n=s["orphans"])))
            if s["needs-reconfirm"]:
                todo.append(("yellow", self.t("st_reconf", n=s["needs-reconfirm"])))
            if fb:
                todo.append(("yellow", self.t("st_fb", n=len(fb))))
            if ch:
                todo.append(("yellow", self.t("st_changes", n=len(ch))))
            if s["untranslated"]:
                todo.append(("grey70", self.t("st_i18n", n=s["untranslated"])))
            if s["draft"]:
                todo.append(("grey70", self.t("st_draft", n=s["draft"])))
            if todo:
                self.say(f"[bold]{self.t('st_problems')}[/]")
                for style, line in todo:
                    self.say(f"  • {line}", style)
                for e in errors[:5]:
                    self.say(f"      {e}", "grey50")
            else:
                self.say(self.t("st_ok"), "green")
            console.print()
            n_rev = len(docs.review_queue())
            opts = []
            if errors or s["orphans"] or s["untranslated"] or s["needs-reconfirm"]:
                opts.append(Choice(self.t("st_fix"), "fix"))
            if fb:
                opts.append(Choice(self.t("st_apply", n=len(fb)), "apply"))
            if n_rev:
                opts.append(Choice(self.t("st_review", n=n_rev), "review"))
            if ch:
                opts.append(Choice(self.t("st_update", n=len(ch)), "update"))
            opts.append(Choice(self.t("st_list"), "list"))
            c = self.sel(self.t("menu"), opts)
            if c is None:
                return
            if c == "fix":
                plan.ensure("doc-fixes", "doc-fixes")
                self.run_unit(plan.get(plan.load(), "doc-fixes"))
            elif c == "apply":
                plan.ensure("review-fixes", "review-fixes")
                self.run_unit(plan.get(plan.load(), "review-fixes"))
            elif c == "review":
                self.do_review()
            elif c == "update":
                self.do_update()
            elif c == "list":
                self.show_doc_list(rows)

    def show_doc_list(self, rows: list[dict]) -> None:
        tbl = Table(show_lines=False, border_style="grey42")
        for col in ("", "Doc", "i18n", "orphan"):
            tbl.add_column(col)
        icon = {"confirmed": "✅", "needs-reconfirm": "⚠️", "draft": "✨"}
        for r in rows:
            tbl.add_row(icon[r["trust"]], r["path"], " ".join(f"{k}:{v}" for k, v in r["i18n"].items() if v != "current"),
                        str(len(r["orphan_sources"]) or ""))
        self.paged(tbl)

    # ---------- review: read each page, confirm it or say what is wrong ----------
    def do_confirm(self) -> bool:            # kept for older plans / menus
        return self.do_review()

    def reviewer(self) -> str | None:
        name = self.prefs.get("reviewer")
        if name:
            return name
        name = self.txt(self.t("your_name"), default=out(["git", "config", "user.name"]) or os.environ.get("USER", "")
                        or os.environ.get("USERNAME", ""))
        if name:
            self.prefs["reviewer"] = name.strip()
            save_json(PREFS, self.prefs)
        return name

    def page_view(self, r: dict, i: int, n: int, show_es: bool, full: bool = False):
        f = (ROOT / r["file"]).resolve()
        es_file = docs.DOCS / "i18n" / "es" / r["path"]
        use_es = show_es and es_file.exists()
        _, body = docs.split_fm((es_file if use_es else f).read_text(encoding="utf-8"))
        lines = body.strip().splitlines()
        limit = max(console.size.height - 22, 10)
        more = len(lines) - limit
        shown = "\n".join(lines if full or more <= 0 else lines[:limit])
        badge = self.t("rv_reconf") if r["trust"] == "needs-reconfirm" else self.t("rv_draft")
        head = Text.from_markup(f"[bold]{self.t('rv_head', i=i, n=n)}[/]  ·  {badge}  ·  [grey62]{r['type'] or 'page'}[/]  ·  "
                                f"[{ORANGE}]{r['file']}[/]")
        parts = [head]
        if r.get("description"):
            parts.append(Text(r["description"], style="italic grey70"))
        if use_es:
            parts.append(Text(self.t("rv_showing_es"), style="grey50"))
        from rich.markdown import Markdown
        parts += [Text(""), Markdown(shown)]
        if not full and more > 0:
            parts.append(Text(self.t("rv_more", n=more), style="grey50"))
        return Panel(Group(*parts), title=r["title"], title_align="left", border_style=ORANGE)

    def do_review(self) -> bool:
        queue = docs.review_queue()
        if not queue:
            self.say(self.t("rv_none"), "green")
            self.pause()
            return True
        reconf = sum(1 for r in queue if r["trust"] == "needs-reconfirm")
        self.say(Panel(Text.from_markup(self.t("rv_intro")), title=self.t("rv_title"), title_align="left", border_style=ORANGE))
        self.say(self.t("rv_count", n=len(queue), r=reconf), "bold")
        if self.sel(self.t("menu"), [Choice(self.t("rv_start"), "go")]) is None:
            return False
        by = self.reviewer()
        if not by:
            return False
        stats = {"c": 0, "f": 0, "s": 0}
        show_es = self.lang == "es"
        finished = True
        for i, r in enumerate(queue, 1):
            while True:
                self.banner()
                console.print(self.page_view(r, i, len(queue), show_es))
                has_es = (docs.DOCS / "i18n" / "es" / r["path"]).exists()
                opts = [Choice(self.t("rv_confirm"), "ok"), Choice(self.t("rv_change"), "change"),
                        Choice(self.t("rv_full"), "full")]
                if has_es:
                    opts.append(Choice(self.t("rv_en") if show_es else self.t("rv_es"), "lang"))
                opts += [Choice(self.t("rv_skip"), "skip"), Choice(self.t("rv_stop"), "stop")]
                c = self.sel(self.t("rv_q"), opts, back=False)
                if c == "full":
                    with console.pager(styles=True):
                        console.print(self.page_view(r, i, len(queue), show_es, full=True))
                    continue
                if c == "lang":
                    show_es = not show_es
                    continue
                if c == "change":
                    txt = self.txt(self.t("rv_what"))
                    if not txt:
                        continue
                    docs.add_feedback(r["file"], txt, by)
                    plan.ensure("review-fixes", "review-fixes")
                    stats["f"] += 1
                elif c == "ok":
                    docs.confirm([r["file"]], by)
                    stats["c"] += 1
                elif c == "skip":
                    stats["s"] += 1
                else:                                   # stop / Esc
                    finished = False
                break
            if not finished:
                break
        self.banner()
        self.say(self.t("rv_sum", **stats), f"bold {ORANGE}")
        if stats["c"] or stats["f"]:
            self.checkpoint(f"review: {stats['c']} confirmed, {stats['f']} change requests")
        if docs.pending_feedback():
            c = self.sel(self.t("menu"), [Choice(self.t("rv_fix_now"), "fix"), Choice(self.t("rv_later"), "later")],
                         back=False)
            if c == "fix":
                self.run_unit(plan.get(plan.load(), "review-fixes"))
        else:
            self.pause()
        return finished

    # ---------- tutorial ----------
    def do_tutorial(self) -> None:
        pages = tutorial.PAGES[self.lang]
        i = 0
        while True:
            self.banner()
            p = pages[i]
            console.print(Panel(Group(Text(p["art"].strip("\n"), style="#ffb38a", no_wrap=True, overflow="crop"), Text(""),
                                      Text(p["text"])),
                                title=f"{p['icon']}  {p['title']}", title_align="left",
                                subtitle=f"{self.t('tu_title')} · {i + 1}/{len(pages)}", subtitle_align="right",
                                border_style=ORANGE))
            opts = []
            if i < len(pages) - 1:
                opts.append(Choice(self.t("tu_next"), "next"))
            else:
                opts.append(Choice(self.t("tu_done"), "done"))
            if i > 0:
                opts.append(Choice(self.t("tu_prev"), "prev"))
            opts.append(Choice(self.t("tu_index"), "index"))
            c = self.sel(" ", opts)
            if c is None or c == "done":
                return
            if c == "next":
                i += 1
            elif c == "prev":
                i -= 1
            else:
                j = self.sel(self.t("tu_index"), [Choice(f"{k + 1:>2}. {q['icon']}  {q['title']}", k) for k, q in enumerate(pages)],
                             default=i)
                if j is not None:
                    i = j

    def do_portal(self) -> None:
        port = int(self.prefs.get("port", 8080))
        while True:
            c = self.sel("🌐 Portal", [Choice(self.t("p_live"), "live"), Choice(self.t("p_build"), "build"),
                                      Choice(self.t("p_up"), "up"), Choice(self.t("p_local"), "local"),
                                      Choice(self.t("p_open"), "open"), Choice(self.t("p_down"), "down")])
            if not c:
                return
            if c == "build":
                self.safe(self.busy, env.portal, total=env.portal_steps())
            elif c in ("live", "up", "local"):
                v = self.txt(self.t("port"), default=str(port))
                if v is None:
                    continue
                port = int(v) if v.isdigit() else port
                self.prefs["port"] = port
                save_json(PREFS, self.prefs)
                if c == "live":
                    url = self.safe(self.busy, env.serve_editor, port, total=1)
                else:
                    if c == "up":
                        ok, why = env.docker_ready()
                        if not ok:
                            if not self.yes(self.t("p_docker_na", why=why), default=True):
                                continue
                            c = "local"
                    if not (CACHE / "site" / "index.html").exists() and \
                            self.safe(self.busy, env.portal, total=env.portal_steps()) is None:
                        continue                                # build failed: the error is already on screen
                    url = self.safe(self.busy, env.docker_up if c == "up" else env.serve_local, port, total=1)
                    if not url and c == "up" and self.yes(self.t("p_docker_fail"), default=True):
                        url = self.safe(self.busy, env.serve_local, port, total=1)
                if url:
                    self.say(self.t("p_running", url=url), "green")
                    env.open_url(url)
                    return True
            elif c == "open":
                env.open_url(f"http://localhost:{port}")
            elif c == "down":
                env.docker_down()

    def do_wikis(self) -> None:
        while True:
            rows = env.wikis()
            tbl = Table(title=self.t("w_title"), title_justify="left", border_style="grey42", show_header=False)
            for w in rows:
                if not w["chosen"]:
                    state = f"[grey50]{self.t('w_off')}[/]"
                elif w["pages"]:
                    state = self.t("w_pages", n=w["pages"]) + (f" [yellow]· {self.t('w_stale')}[/]" if w["stale"] else "")
                else:
                    state = f"[grey50]{self.t('w_none')}[/]" + ("" if w["ready"] else f" [yellow]· {self.t('w_need_brief')}[/]")
                tbl.add_row(w["repo"], state, f"[grey50]{w['unit'] or ''}[/]")
            self.say(tbl)
            chosen = [w for w in rows if w["chosen"] and w["cloned"]]
            if not chosen:
                self.say(self.t("w_none_chosen"), "yellow")
            c = self.sel(self.t("m_wikis"), [Choice(self.t("w_gen"), "gen", disabled=None if chosen else self.t("w_choose_first")),
                                             Choice(self.t("w_choose"), "choose"), Choice(self.t("w_open"), "open")])
            if not c:
                return
            if c == "open":
                self.open_portal("#/wikis")
                continue
            if c == "choose":
                picked = self.chk(self.t("w_choose_q"), [Choice(w["repo"], w["repo"], checked=w["chosen"]) for w in rows])
                if picked is not None:
                    docs.set_wiki_repos(picked)
                    plan.sync()
                self.banner()
                continue
            if not any(w["ready"] for w in chosen):
                self.say(self.t("w_none_ready", repos=", ".join(w["repo"] for w in chosen)), "yellow")
                self.pause()
                self.banner()
                continue
            picked = self.chk(self.t("w_pick"), [Choice(w["repo"], w["repo"], disabled=None if w["ready"] else self.t("w_need_brief"))
                                                 for w in chosen])
            if not picked:
                continue
            engine = self.wiki_engine()
            if not engine:
                continue
            for i, repo in enumerate(picked):
                try:
                    ok = self.busy(env.openwiki_generate, repo, engine=engine)
                except env.WikiAbort as e:          # quota / login: the rest would fail the same way
                    left = picked[i + 1:]
                    console.print(Panel(str(e) + (f"\n{self.t('w_skipped', repos=', '.join(left))}" if left else ""),
                                        title=self.t("error"), border_style="red"))
                    break
                except Exception as e:  # noqa: BLE001
                    console.print(Panel(str(e), title=self.t("error"), border_style="red"))
                    ok = False
                self.say(self.t("w_done", repo=repo) if ok else self.t("w_fail", repo=repo), "green" if ok else "yellow")
            self.pause()
            self.banner()

    def do_uninstall(self) -> str | None:
        """Undo the whole project (lib/uninstall.py). Returns 'gone' once cam-docs is deleted."""
        from . import uninstall
        why = uninstall.guard()
        if why:
            self.say(Panel(why, border_style="yellow"))
            self.pause()
            return None
        user_level = self.yes(self.t("u_global"), default=False)
        if user_level is None:
            return None
        self.banner()
        rows = Text()
        for s in uninstall.steps(include_global=user_level):
            rows.append(f"  • {s.label}\n", style="yellow" if s.kind in ("delete", "user") else "")
        rows.append(f"\n{self.t('u_keep')}:\n", style="bold")
        for t in uninstall.untouched():
            rows.append(f"  · {t}\n", style="grey62")
        self.say(Panel(rows, title=self.t("u_preview"), title_align="left", border_style="red"))
        name = docs.workspace()["project"]["name"]
        typed = self.txt(self.t("u_confirm", name=name))
        if typed is None or typed.strip().casefold() != name.strip().casefold():
            self.say(self.t("u_cancel"), "yellow")
            self.pause()
            return None
        zipped = self.busy(uninstall.run, include_global=user_level)
        self.say(self.t("u_done", ws=WORKSPACE), "green")
        if zipped:
            self.say(self.t("u_backup", path=zipped))
        self.pause()
        return "gone"

    def wiki_engine(self) -> str | None:
        engines = env.wiki_engines()
        if not engines:
            self.say(Panel(self.t("w_no_engine"), border_style="yellow"))
            return None
        if len(engines) == 1:
            return engines[0]
        return self.sel(self.t("w_engine"), [Choice(self.t(f"w_eng_{e}"), e) for e in engines])

    def open_portal(self, hash_: str = "") -> None:
        """The live portal, started if it is not running yet."""
        import socket
        port = int(self.prefs.get("port", 8080))
        with socket.socket() as sck:
            up = sck.connect_ex(("127.0.0.1", port)) == 0
        url = f"http://localhost:{port}" if up else self.safe(self.busy, env.serve_editor, port, total=1)
        if url:
            env.open_url(url + "/" + hash_)

    def retry_missing(self, missing: list[str]) -> None:
        """A repo with a url but no .git after sync almost always means missing/expired credentials —
        offer to add a token and resync right here instead of leaving the user to guess why it failed."""
        while missing:
            self.say(self.t("s_missing", repos=", ".join(missing)), "yellow")
            if not self.yes(self.t("s_token_retry"), default=True):
                return
            host = creds.host_of(next(r["url"] for r in docs.workspace()["repos"] if r["name"] == missing[0]))
            self.banner()
            self.add_token(host)
            self.banner()
            self.safe(self.busy, lambda log: docs.sync_repos(log))
            missing = [n for n in missing if not (repo_dir(n) / ".git").exists()]

    def do_repos(self) -> None:
        ws = docs.workspace()
        before = {r["name"] for r in ws["repos"]}
        self.fr_repos(ws)
        if {r["name"] for r in docs.workspace()["repos"]} != before:
            self.safe(self.busy, lambda log: docs.sync_repos(log))
            self.retry_missing([r["name"] for r in docs.workspace()["repos"]
                                 if r.get("url") and not (repo_dir(r["name"]) / ".git").exists()])
            for n in docs.repo_names():
                if (repo_dir(n) / ".git").exists() and not env.repo_graph(n).exists():
                    self.safe(self.busy, env.wire_one, n)
            plan.sync()

    def repo_pointer(self) -> None:
        """Asked once, remembered in workspace.yaml: the only thing Camarones may add to a service repo."""
        ws = docs.workspace()
        if "repo_pointer" in ws["project"] or not CAM_LAYOUT:
            return
        ws["project"]["repo_pointer"] = bool(self.yes(self.t("pointer_ask"), default=False))
        docs.save_workspace(ws)

    def do_setup(self) -> bool:
        ws = docs.workspace()
        if self.fr_tools(ws) == BACK:
            return False
        self.repo_pointer()
        self.banner()
        ok = self.safe(self.busy, env.setup, total=env.setup_steps())
        plan.sync()
        if ok:
            plan.set_status("setup", "done", "wizard")
        self.pause()
        return bool(ok)

    def do_ci(self) -> bool:
        forge = self.sel(self.t("ci_forge"), [Choice("GitLab", "gitlab"), Choice("GitHub", "github")],
                         default=env.detect_forge())
        if not forge:
            return False
        self.safe(self.busy, env.install_ci, forge)
        self.say(self.t("ci_done"), "green")
        self.pause()
        return True

    def do_model(self) -> None:
        agent = "claude"
        if which("claude") and which("codex"):
            agent = self.sel(self.t("which_model_agent"), [Choice("Claude Code", "claude"), Choice("Codex", "codex")])
            if not agent:
                return
        elif which("codex") and not which("claude"):
            agent = "codex"
        if agent == "codex":
            cur = self.prefs.get("codex_model", CODEX_MODEL_DEFAULT)
            c = self.txt(self.t("which_codex_model"), default=cur)
            if c:
                self.prefs["codex_model"] = c
                save_json(PREFS, self.prefs)
                self.say(self.t("model_set", model=c), "green")
                time.sleep(1)
            return
        cur = self.prefs.get("model", "sonnet")
        c = self.sel(self.t("which_model"), [Choice(m.capitalize(), m) for m in MODELS], default=cur)
        if c:
            self.prefs["model"] = c
            save_json(PREFS, self.prefs)
            self.say(self.t("model_set", model=c.capitalize()), "green")
            time.sleep(1)

    def do_lang(self) -> None:
        c = self.sel("🌍 Idioma / Language", [Choice("Español", "es"), Choice("English", "en")], default=self.lang)
        if c:
            self.lang = c
            self.prefs["lang"] = c
            save_json(PREFS, self.prefs)
            self.say("✔ " + ("Idioma: español (también para las sesiones con IA)" if c == "es"
                             else "Language: English (AI sessions too)"), "green")
            time.sleep(1)


def resume_step(state: dict) -> int:
    """Where the first run continues: by step id, or by index for firstrun.json files written before 3.3."""
    if state.get("name") in STEPS:
        return STEPS.index(state["name"])
    i = int(state.get("step", 0))
    return STEPS.index(LEGACY_STEPS[i]) if 0 <= i < len(LEGACY_STEPS) else min(max(i, 0), len(STEPS) - 1)


def claude_history(cwd: Path) -> bool:
    """Whether Claude Code has a saved conversation for `cwd` (its projects dir is the path with / and . → -)."""
    key = "".join(c if c.isalnum() else "-" for c in str(cwd.resolve()))
    return any((HOME / ".claude" / "projects" / key).glob("*.jsonl"))


def copy_clipboard(text: str) -> bool:
    cmd = ["clip"] if IS_WIN else (["pbcopy"] if IS_MAC else (["wl-copy"] if which("wl-copy") else ["xclip", "-selection", "clipboard"]))
    if not which(cmd[0]):
        return False
    try:
        subprocess.run(cmd, input=text.encode("utf-16le" if IS_WIN else "utf-8"), check=True)
        return True
    except Exception:  # noqa: BLE001
        return False


def install_from_kit_folder(kit_dir: Path, ask: bool = True) -> bool:
    """The kit sits in a subfolder of the project (unzipped there, or staged for an upgrade): move it up one level.
    Keeps the project's .camarones/workspace.yaml and .camarones/.cache/; never touches docs/."""
    import shutil
    w = W()
    parent = kit_dir.parent
    if ask and sys.stdin.isatty() and not w.yes(w.t("install_here", kit=kit_dir.name, parent=parent)):
        return False
    for item in kit_dir.iterdir():
        dst = parent / item.name
        if item.name == ".camarones" and dst.exists():          # kit upgrade: keep project config and caches
            for keep in ("workspace.yaml", ".cache"):
                if (dst / keep).exists() and not (item / keep).exists():
                    shutil.move(str(dst / keep), str(item / keep))
            shutil.rmtree(dst, ignore_errors=True)
        if dst.exists() and item.is_file():
            if dst.read_bytes() == item.read_bytes():
                continue                                      # same launcher: leave the running one alone
            dst.unlink()
        if not dst.exists():
            shutil.move(str(item), str(dst))
    shutil.rmtree(kit_dir, ignore_errors=True)
    from . import upgrade
    try:
        upgrade.cleanup_legacy(log=lambda m: console.print(m, style="grey62"))
    except Exception:  # noqa: BLE001
        pass
    console.print(w.t("installed_here", parent=parent), style=f"bold {ORANGE}")
    if not IS_WIN:
        p = parent / "camaron.command"
        if p.exists():
            p.chmod(0o755)
    return True


def offer_upgrade() -> bool:
    """Wizard start: a newer kit (folder or zip) is next to the project → offer to install it. True = upgraded."""
    from . import upgrade
    try:
        c = upgrade.newest()
    except Exception:  # noqa: BLE001
        return False
    if not c or not sys.stdin.isatty():
        return False
    w = W()
    console.print(Panel(w.t("up_found", new=c["version"], cur=upgrade.current(), where=str(c["path"])),
                        title="🦐 Camarón", border_style=ORANGE))
    if not w.yes(w.t("up_q"), default=True):
        return False
    kit_dir = upgrade.stage(c)
    install_from_kit_folder(kit_dir, ask=False)
    console.print(w.t("up_done", new=c["version"]), style=f"bold {ORANGE}")
    return True
