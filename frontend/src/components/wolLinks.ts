/**
 * wolLinks.ts
 * Purpose: links into wol.jw.org that the frontend can build without asking
 * the server, so a citation is clickable before (or without) resolution.
 */

export const WOL_SEARCH = 'https://wol.jw.org/en/wol/l/r1/lp-e?q='

/** Where a citation such as "w12 11/1 23" can be looked up on wol.jw.org. */
export const searchLink = (ref: string) => WOL_SEARCH + encodeURIComponent(ref)
