import { core } from './core.js'

// Historias (#/stories): the story wizard. Its pure helpers are in stories.js; the screen itself comes with the wizard.
// Until then the address resolves to this heading, so the zone, the route and the router test have a view to show.
export default function Stories() {
  return (
    <section className="view stories">
      <h1>{core.t('view.stories')}</h1>
      <p className="lede">{core.t('viewd.stories')}</p>
    </section>
  )
}
