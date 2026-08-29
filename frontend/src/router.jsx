/* Minimal history router — two routes, no dependency. SPA rewrites are already
   configured for Netlify and Vercel so deep links to /wiki resolve. */
import { createContext, useCallback, useContext, useEffect, useState } from "react";

const RouterCtx = createContext({ path: "/", navigate: () => {} });

export function Router({ children }) {
  const [path, setPath] = useState(
    typeof window !== "undefined" ? window.location.pathname || "/" : "/"
  );

  useEffect(() => {
    const onPop = () => setPath(window.location.pathname || "/");
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const navigate = useCallback((to) => {
    if (to === window.location.pathname) return;
    window.history.pushState({}, "", to);
    setPath(to);
    window.scrollTo(0, 0);
  }, []);

  return <RouterCtx.Provider value={{ path, navigate }}>{children}</RouterCtx.Provider>;
}

export function useRouter() {
  return useContext(RouterCtx);
}

export function Link({ to, className, activeClassName, children, ...rest }) {
  const { path, navigate } = useRouter();
  const active = to === "/" ? path === "/" : path.startsWith(to);
  const onClick = (e) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
    e.preventDefault();
    navigate(to);
  };
  const cls = [className, active ? activeClassName : ""].filter(Boolean).join(" ");
  return (
    <a href={to} onClick={onClick} className={cls || undefined} {...rest}>
      {children}
    </a>
  );
}
