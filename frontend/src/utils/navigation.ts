export type PublicRoute = 'landing' | 'login' | 'register';

export function getPublicRoute(): PublicRoute {
  const path = window.location.pathname.replace(/\/$/, '') || '/';
  if (path === '/login') return 'login';
  if (path === '/register') return 'register';
  return 'landing';
}

export function navigateTo(route: PublicRoute) {
  const path = route === 'landing' ? '/' : `/${route}`;
  window.history.pushState({}, '', path);
  window.dispatchEvent(new PopStateEvent('popstate'));
}
