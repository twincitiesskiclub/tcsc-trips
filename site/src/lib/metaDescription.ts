// Meta-description trimmer: search engines truncate snippets around 155-160
// characters, while intro-derived descriptions (the about intro runs 500+
// chars) arrive much longer. Whitespace collapses first because YAML folded
// scalars carry newlines.
//
// Boundary preference: cut at the last real sentence end inside the window
// when one lands past the halfway mark (a clean full sentence reads better
// than a longer fragment); otherwise cut at a word boundary, strip trailing
// punctuation, and add an ellipsis.

// Periods after these tokens are abbreviations, not sentence ends (the
// community intro's "Minneapolis / St. Paul" was the motivating bug).
const ABBREVIATION = /(^|\s)(St|Mt|Mr|Mrs|Ms|Dr|vs|etc|Jr|Sr|No)$/;

function lastSentenceEnd(window: string): number {
  const re = /[.!?](?= )/g;
  let best = -1;
  for (let m = re.exec(window); m !== null; m = re.exec(window)) {
    if (window[m.index] === '.' && ABBREVIATION.test(window.slice(0, m.index))) continue;
    best = m.index;
  }
  return best;
}

export function metaDescription(text: string, max = 155): string {
  const clean = text.replace(/\s+/g, ' ').trim();
  if (clean.length <= max) return clean;
  const window = clean.slice(0, max);
  const sentenceEnd = lastSentenceEnd(window);
  if (sentenceEnd >= max * 0.5) return window.slice(0, sentenceEnd + 1);
  const wordEnd = window.lastIndexOf(' ');
  const cut = wordEnd > 0 ? window.slice(0, wordEnd) : window;
  return cut.replace(/[\s,;:–—-]+$/, '') + '…';
}
