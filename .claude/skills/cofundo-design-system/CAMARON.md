# Camarón portal: how this design system is adapted

The Camarón portal (`.camarones/portal/app/`) uses Cofundo's visual language: tokens, type, components and the
console density. The product stays **Camarón**. Where this note and the rest of the package differ, this note wins
for the portal.

- **Wordmark**: «camarón», lowercase, Big Shoulders 700. No «cofundo» wordmark and no Bricolage Grotesque. The
  favicon stays `portal/app/public/legacy/favicon.svg`.
- **Dark theme**: allowed. The package has none; the portal derives one in `portal/app/public/theme/tokens.css`
  (same token names, values chosen to keep 4.5:1 for text). `src/tokens.test.js` enforces the contrast in both themes.
- **Voice**: the kit's `AGENTS.md` §3 (the intern shrimp: at most one joke per screen, none in errors, warnings,
  decisions or destructive actions; every string in `es` and `en`). Cofundo's copy rules that agree with it apply
  too: no copy without a way out ("No data", "Something went wrong"), a server rejection shown as it is, figures from
  real data only, buttons that say what happens.
- **Legal rules**: the package's three legal rules are about Cofundo's sales product and do not apply here.
- **Fonts**: self-hosted in `portal/app/public/theme/fonts/` (OFL). Never Google Fonts: the portal is deployed on
  internal networks and makes no request to third parties.
- **Density**: the portal is a console. Use the `-sm` sizes, `--consola-radio-*` for cards and controls, and keep
  the display sizes (`--text-display-*`) for the Home hero only.
- **Icons**: there is no icon system. Text glyphs (`→`) and the existing trust labels only.
