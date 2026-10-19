import { useEffect, useState, useCallback } from 'react';
import { getHealth } from '../services/api';

/**
 * Hook to poll the backend health endpoint and return connection status.
 * @param {number} intervalMs – polling interval in milliseconds (default 30 000)
 */
export function useHealth(intervalMs = 30_000) {
  const [status, setStatus] = useState('checking'); // 'online' | 'offline' | 'checking'
  const [lastChecked, setLastChecked] = useState(null);

  const check = useCallback(async () => {
    setStatus('checking');
    try {
      await getHealth();
      setStatus('online');
    } catch {
      setStatus('offline');
    } finally {
      setLastChecked(new Date());
    }
  }, []);

  useEffect(() => {
    check();
    const id = setInterval(check, intervalMs);
    return () => clearInterval(id);
  }, [check, intervalMs]);

  return { status, lastChecked, retry: check };
}

/**
 * Generic data-fetching hook.
 * @param {Function} fetchFn – async function that returns data
 * @param {Array}    deps    – dependency array for re-fetching
 */
export function useFetch(fetchFn, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const execute = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchFn();
      setData(result);
    } catch (err) {
      setError(err.message || 'Failed to fetch data');
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    execute();
  }, [execute]);

  return { data, loading, error, refetch: execute };
}
