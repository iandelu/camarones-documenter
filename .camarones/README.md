# 🦐 Camarón

*Camarón que se duerme, se lo lleva la corriente.*

**ES** — Kit + asistente para documentar un proyecto multi-repo con Claude Code o Codex, por sesiones.
1. Descomprime este zip en la carpeta donde están (o estarán) los repos del proyecto.
2. Abre el asistente: **macOS** doble clic en `camaron.command` · **Windows** doble clic en `camaron.cmd`.
   **¿macOS lo bloquea?** Abre Terminal en la carpeta y ejecuta `sh camaron.command` una vez (quita la cuarentena; luego el doble clic funciona).
   **¿Windows lo bloquea?** Antes de descomprimir: clic derecho en el zip → Propiedades → **Desbloquear**. Ya descomprimido: PowerShell en la carpeta → `Get-ChildItem -Recurse | Unblock-File`. SmartScreen: "Más información" → "Ejecutar de todas formas".
3. Sigue los pasos. ¿Nuevo? En el menú: **📖 Tutorial: ¿qué es cada herramienta?** (también en `.camarones/TUTORIAL.md`).
   Guía de comandos: `docs/guides/tutorial.md` (ES: `docs/i18n/es/guides/tutorial.md`).

**Actualizar el kit**: deja el zip nuevo en la carpeta del proyecto (o en Descargas) y abre el asistente: detecta la versión
nueva y se actualiza conservando configuración, plan y documentación. Si tu versión es anterior a 2.4 (no lo detecta),
descomprime el zip nuevo en la carpeta del proyecto **sobrescribiendo** los archivos, o en una subcarpeta y abre el
`camaron.command`/`camaron.cmd` de esa subcarpeta. La versión aparece junto al título del asistente.

**EN** — Kit + wizard to document a multi-repo project with Claude Code or Codex, session by session.
1. Extract this zip into the folder where the project's repos live (or will live).
2. Open the wizard: **macOS** double-click `camaron.command` · **Windows** double-click `camaron.cmd`.
   **macOS blocks it?** Open Terminal in the folder and run `sh camaron.command` once (clears the quarantine; double-click works afterwards).
   **Windows blocks it?** Before extracting: right-click the zip → Properties → **Unblock**. Already extracted: PowerShell in the folder → `Get-ChildItem -Recurse | Unblock-File`. SmartScreen: "More info" → "Run anyway".
3. Follow the steps. New here? Menu → **📖 Tutorial: what is each tool?** (also `.camarones/TUTORIAL.md`).
   Command guide: `docs/guides/tutorial.md`.

**Upgrading the kit**: drop the new zip into the project folder (or Downloads) and open the wizard: it detects the newer
version and upgrades, keeping config, plan and docs. From versions before 2.4 (no detection): extract the new zip into the
project folder **overwriting** files, or into a subfolder and open that subfolder's launcher. The version is shown next
to the wizard title.

Tools used (all permissive licenses): OpenWiki (MIT), LikeC4 (MIT), graphify (MIT/Apache-2.0), marked (MIT), DOMPurify (Apache-2.0/MPL-2.0), Mermaid (MIT),
mermaid-cli (MIT), gitleaks (MIT), nginx (BSD-2), uv (MIT/Apache-2.0), rich (MIT), questionary (MIT).
