/**
 * Persistência de cache React Query no localStorage
 * Salva dados entre sessões — reduz chamadas à API e melhora UX offline
 */

const CACHE_PREFIX = "jrdev1_cache_";
const CACHE_TTL_MS = 10 * 60 * 1000; // 10 min padrão

interface CacheEntry<T> {
  data: T;
  timestamp: number;
  ttl: number;
}

export function saveCache<T>(key: string, data: T, ttl = CACHE_TTL_MS): void {
  try {
    const entry: CacheEntry<T> = { data, timestamp: Date.now(), ttl };
    localStorage.setItem(CACHE_PREFIX + key, JSON.stringify(entry));
  } catch {
    // localStorage cheio ou indisponível — ignorar silenciosamente
  }
}

export function loadCache<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(CACHE_PREFIX + key);
    if (!raw) return null;
    const entry: CacheEntry<T> = JSON.parse(raw);
    if (Date.now() - entry.timestamp > entry.ttl) {
      localStorage.removeItem(CACHE_PREFIX + key);
      return null;
    }
    return entry.data;
  } catch {
    return null;
  }
}

export function clearCache(key?: string): void {
  if (key) {
    localStorage.removeItem(CACHE_PREFIX + key);
    return;
  }
  // Limpar todo cache JRDEV1
  Object.keys(localStorage)
    .filter((k) => k.startsWith(CACHE_PREFIX))
    .forEach((k) => localStorage.removeItem(k));
}

export function getCacheStats(): { keys: string[]; totalBytes: number } {
  const keys = Object.keys(localStorage).filter((k) => k.startsWith(CACHE_PREFIX));
  const totalBytes = keys.reduce((s, k) => s + (localStorage.getItem(k)?.length ?? 0), 0);
  return { keys: keys.map((k) => k.replace(CACHE_PREFIX, "")), totalBytes };
}
