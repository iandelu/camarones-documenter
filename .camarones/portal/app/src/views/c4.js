// Pure pieces of the Architecture view's element panel.

// Elements still to review (an AI draft, or never confirmed) come first; confirmed ones go to a folded section. One
// tagged both ways (#ai-draft left on a confirmed element) is still to review.
export function splitElements(elements) {
  const done = (e) => e.confirmed && !e.draft
  return { pending: elements.filter((e) => !done(e)), confirmed: elements.filter(done) }
}
