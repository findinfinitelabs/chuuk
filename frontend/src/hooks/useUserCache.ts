import { useState, useEffect, useCallback, useRef } from 'react'

/**
 * A custom hook for caching user-specific data in localStorage.
 * Data is tied to the user's email so each user has their own cache.
 * Data persists across sessions and page navigations.
 * 
 * @param key - The cache key (will be prefixed with user email)
 * @param initialValue - Default value if no cached data exists
 * @param userEmail - The current user's email (used as cache namespace)
 * @returns [cachedValue, setCachedValue, clearCache]
 */
export function useUserCache<T>(
  key: string,
  initialValue: T,
  userEmail: string | null | undefined
): [T, (value: T | ((prev: T) => T)) => void, () => void] {
  // Store initial value in a ref to avoid re-render loops
  const initialValueRef = useRef(initialValue)
  
  // Build the cache key with user email prefix
  const getCacheKey = useCallback(() => {
    const userPrefix = userEmail || 'anonymous'
    return `chuuk_cache_${userPrefix}_${key}`
  }, [key, userEmail])

  // Initialize state from localStorage or use initial value
  const [value, setValue] = useState<T>(() => {
    if (typeof window === 'undefined') return initialValue
    
    try {
      const cacheKey = getCacheKey()
      const cached = localStorage.getItem(cacheKey)
      if (cached) {
        const parsed = JSON.parse(cached)
        // Check if cache has expired (default: 30 days)
        if (parsed.expiry && Date.now() > parsed.expiry) {
          localStorage.removeItem(cacheKey)
          return initialValue
        }
        return parsed.data
      }
    } catch (error) {
      console.warn(`Error reading cache for ${key}:`, error)
    }
    return initialValue
  })

  // Update localStorage when value changes
  useEffect(() => {
    if (typeof window === 'undefined') return
    
    try {
      const cacheKey = getCacheKey()
      const cacheData = {
        data: value,
        timestamp: Date.now(),
        expiry: Date.now() + (30 * 24 * 60 * 60 * 1000) // 30 days
      }
      localStorage.setItem(cacheKey, JSON.stringify(cacheData))
    } catch (error) {
      console.warn(`Error saving cache for ${key}:`, error)
    }
  }, [value, key, getCacheKey])

  // Re-read from cache when user changes
  useEffect(() => {
    if (typeof window === 'undefined') return
    
    try {
      const cacheKey = getCacheKey()
      const cached = localStorage.getItem(cacheKey)
      if (cached) {
        const parsed = JSON.parse(cached)
        if (!parsed.expiry || Date.now() <= parsed.expiry) {
          setValue(parsed.data)
          return
        }
      }
      setValue(initialValueRef.current)
    } catch (error) {
      console.warn(`Error reading cache for ${key}:`, error)
      setValue(initialValueRef.current)
    }
  }, [userEmail, key, getCacheKey])

  // Clear cache function
  const clearCache = useCallback(() => {
    try {
      const cacheKey = getCacheKey()
      localStorage.removeItem(cacheKey)
      setValue(initialValueRef.current)
    } catch (error) {
      console.warn(`Error clearing cache for ${key}:`, error)
    }
  }, [key, getCacheKey])

  return [value, setValue, clearCache]
}

/**
 * Get the current user's email from the auth status endpoint.
 * This is a helper for components that don't have access to the user context.
 */
export async function getCurrentUserEmail(): Promise<string | null> {
  try {
    const response = await fetch('/api/auth/status')
    const data = await response.json()
    return data.authenticated ? data.user?.email : null
  } catch {
    return null
  }
}
