import { useEffect, useRef } from "react";

export function usePolling(fn, interval, active) {
  const savedFn = useRef(fn);
  useEffect(() => { savedFn.current = fn; }, [fn]);
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => savedFn.current(), interval);
    return () => clearInterval(id);
  }, [interval, active]);
}
