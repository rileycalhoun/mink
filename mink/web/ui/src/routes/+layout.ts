// Client-rendered SPA: the FastAPI app serves index.html as the fallback for
// every route, so nothing is prerendered and there is no SSR.
export const prerender = false;
export const ssr = false;
