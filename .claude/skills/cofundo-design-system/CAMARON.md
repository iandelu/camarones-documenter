# Camarón portal: how this design system is adapted

The Camarón portal (`.camarones/portal/app/`) uses Cofundo's visual language: tokens, type, components and the
console density. The product stays **Camarón**. Where this note and the rest of the package differ, this note wins
for the portal.

- **Wordmark**: «camarón», lowercase, Big Shoulders 700. No «cofundo» wordmark and no Bricolage Grotesque. The
  favicon stays `portal/app/public/favicon.svg`: the shrimp, coral (`--color-aurora-coral`) on an ink tile. It is
  the one drawing of the mark; `scripts/icons.py` renders the desktop app's icons from it (`desktop/icon.png`, and
  `desktop/icon-mac.png` on the dock's grid). Change the favicon, run the script, commit all three.
- **Dark theme**: allowed. The package has none; Camarón derives one in `.camarones/ui/theme/tokens.css` (same
  token names, values chosen to keep 4.5:1 for text). `ui/theme/tokens.test.js` enforces the contrast in both themes.
- **Radii**: square corners, not pills. Buttons, fields and chips use 3–4px, cards and dialogs 6px; the
  `--radius-*` and `--consola-radio-*` tokens carry those values and `tokens.test.js` keeps them at 6px or less.
- **Brand**: the wordmark with the project name stacked under it, small and dim (`Brand` in `.camarones/ui`).
- **Breadcrumbs** on every view, in the portal and in the desktop app.
- **Voice**: the kit's `AGENTS.md` §3 (the intern shrimp: at most one joke per screen, none in errors, warnings,
  decisions or destructive actions; every string in `es` and `en`). Cofundo's copy rules that agree with it apply
  too: no copy without a way out ("No data", "Something went wrong"), a server rejection shown as it is, figures from
  real data only, buttons that say what happens.
- **Legal rules**: the package's three legal rules are about Cofundo's sales product and do not apply here.
- **Fonts**: self-hosted in `.camarones/ui/theme/fonts/` (OFL). Never Google Fonts: the portal is deployed on
  internal networks and makes no request to third parties.
- **Density**: the portal is a console. Use the `-sm` sizes, `--consola-radio-*` for cards and controls, and keep
  the display sizes (`--text-display-*`) for the Home hero only.
- **Icons**: there is no icon system. Text glyphs (`→`) and the existing trust labels only. One approved exception: the
  desktop start screen (`desktop/renderer/src/Hub.jsx`) draws its two option icons (folder, people) as inline SVG; the
  portal keeps text glyphs.
  A second approved exception: the first-run wizard (`desktop/renderer/src/sections/Start.jsx`) draws its external-link,
  edit and check icons as inline SVG, aria-hidden, in currentColor; the rest of the app keeps text glyphs.
  A third approved exception: the portal's freshness icons (`FreshIcon` in `portal/app/src/views/Sources.jsx`: fresh,
  changed, missing, unchecked) on a doc page's header pill and its Sources card, inline SVG, aria-hidden, in
  currentColor, always next to their word or with it as the link's label.
