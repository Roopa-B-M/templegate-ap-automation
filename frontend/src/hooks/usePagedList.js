import { useCallback, useEffect, useRef, useState } from 'react';
import { useSnackbar } from '../context/SnackbarContext';
import { getApiErrorMessage } from '../utils/format';

/**
 * Turns a `fetchFn(page, pageSize)` (expected to resolve to a DRF paginated
 * payload `{count, results}`) into loading/rows/count state for DataTable.
 * Whenever any entry of `watch` changes, the list resets to page 0 and reloads.
 * Read failures raise a global snackbar plus an `error` state for inline display.
 */
export default function usePagedList(fetchFn, watch = [], options = {}) {
  const { pageSize: initialPageSize = 10 } = options;
  const { showSnackbar } = useSnackbar();
  const [rows, setRows] = useState([]);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(initialPageSize);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const requestRef = useRef(0);

  const load = useCallback(
    async (nextPage = page, nextPageSize = pageSize) => {
      const requestId = ++requestRef.current;
      setLoading(true);
      try {
        const data = await fetchFn(nextPage, nextPageSize);
        if (requestId !== requestRef.current) return;
        setRows(data?.results || []);
        setCount(typeof data?.count === 'number' ? data.count : (data?.results || []).length);
        setError(null);
      } catch (e) {
        if (requestId !== requestRef.current) return;
        setError(e);
        setRows([]);
        setCount(0);
        showSnackbar(getApiErrorMessage(e), 'error');
      } finally {
        if (requestId === requestRef.current) setLoading(false);
      }
    },
    [fetchFn, page, pageSize, showSnackbar]
  );

  useEffect(() => {
    load(page, pageSize);
  }, [load, page, pageSize]);

  // Reset back to the first page whenever watched inputs change.
  const watchKey = JSON.stringify(watch);
  const previousWatchKey = useRef(watchKey);
  useEffect(() => {
    if (previousWatchKey.current !== watchKey) {
      previousWatchKey.current = watchKey;
      setPage(0);
    }
  }, [watchKey]);

  const changePageSize = useCallback((size) => {
    setPageSize(size);
    setPage(0);
  }, []);

  return {
    rows,
    count,
    page,
    pageSize,
    loading,
    error,
    setPage,
    changePageSize,
    reload: useCallback(() => load(page, pageSize), [load, page, pageSize]),
  };
}
