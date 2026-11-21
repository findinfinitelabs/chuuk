/**
 * talkPaginate.ts — packs measured print blocks onto fixed-height pages for TalkPrint.tsx.
 */
const HEADING = new Set(['title', 'section', 'point'])

/** Pack measured block heights onto pages of `limit` height; a heading is
 *  carried to the next page when it would otherwise end a page alone. */
export function paginate(heights: number[], kinds: string[], limit: number): number[][] {
  const pages: number[][] = []
  let page: number[] = []
  let used = 0
  heights.forEach((h, i) => {
    if (page.length && used + h > limit) {
      // Do not leave a heading stranded at the foot of the page.
      const carried: number[] = []
      while (page.length && HEADING.has(kinds[page[page.length - 1]])) carried.unshift(page.pop()!)
      if (page.length) pages.push(page)
      page = carried
      used = carried.reduce((s, k) => s + heights[k], 0)
    }
    page.push(i)
    used += h
  })
  if (page.length) pages.push(page)
  return pages
}

