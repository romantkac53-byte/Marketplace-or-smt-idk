import { useCallback, useEffect, useState } from 'react'

/**
 * Загрузка данных для страницы:
 *   const { data, loading, error, reload } = useLoad(() => ordersApi.get(id), [id])
 * Если параметры изменились, пока шёл старый запрос, его ответ игнорируется.
 */
export function useLoad(loader, deps) {
  const [state, setState] = useState({ data: null, loading: true, error: null })
  const [version, setVersion] = useState(0)

  useEffect(() => {
    let cancelled = false
    setState((prev) => ({ ...prev, loading: true, error: null }))
    loader()
      .then((data) => !cancelled && setState({ data, loading: false, error: null }))
      .catch((error) => !cancelled && setState({ data: null, loading: false, error }))
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, version])

  const reload = useCallback(() => setVersion((v) => v + 1), [])
  // setData — обновить данные ответом действия (оплата, отмена) без повторной загрузки
  const setData = useCallback((data) => setState({ data, loading: false, error: null }), [])
  return { ...state, reload, setData }
}
