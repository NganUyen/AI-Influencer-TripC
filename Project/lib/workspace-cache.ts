/**
 * Simple in-memory workspace cache
 * Reduces API calls on tab switches within cache TTL
 * No external dependencies - pure TypeScript
 */

type CachedWorkspace = {
  data: any;
  timestamp: number;
};

let cache: CachedWorkspace | null = null;
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

/**
 * Get cached workspace data if still valid
 * @returns Cached data or null if expired/missing
 */
export function getWorkspaceCache() {
  if (!cache) return null;

  const age = Date.now() - cache.timestamp;
  if (age > CACHE_TTL_MS) {
    cache = null;
    return null;
  }

  return cache.data;
}

/**
 * Store workspace data in cache
 */
export function setWorkspaceCache(data: any) {
  cache = {
    data,
    timestamp: Date.now(),
  };
}

/**
 * Clear cache (call on mutations)
 */
export function clearWorkspaceCache() {
  cache = null;
}

/**
 * Get cache age in seconds (for debugging)
 */
export function getCacheAge() {
  if (!cache) return null;
  return Math.round((Date.now() - cache.timestamp) / 1000);
}
