import { useCallback, useEffect, useState } from "react"

/** Tiny client-side routing: two pages don't need a router library. */
export function usePath(): [string, (to: string) => void] {
  const [path, setPath] = useState(() => window.location.pathname)

  useEffect(() => {
    const onPop = () => setPath(window.location.pathname)
    window.addEventListener("popstate", onPop)
    return () => window.removeEventListener("popstate", onPop)
  }, [])

  const go = useCallback((to: string) => {
    if (to === window.location.pathname) return
    window.history.pushState(null, "", to)
    setPath(to)
    window.scrollTo({ top: 0 })
  }, [])

  return [path, go]
}
