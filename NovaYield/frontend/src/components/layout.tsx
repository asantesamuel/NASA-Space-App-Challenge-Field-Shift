import { useEffect, useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/auth-context';

type SidebarIconName = 'plots' | 'setup' | 'analysis' | 'climate' | 'rotations' | 'menu' | 'close';

function SidebarIcon({ name }: { name: SidebarIconName }) {
  const shared = {
    'aria-hidden': true as const,
    className: 'sidebar-icon',
    fill: 'none',
    stroke: 'currentColor',
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    strokeWidth: 1.8,
    viewBox: '0 0 24 24',
  };

  if (name === 'plots') {
    return <svg {...shared}><rect x="3.5" y="4" width="17" height="16" rx="2" /><path d="M8 4v16M16 4v16M3.5 10h17M3.5 15h17" /></svg>;
  }
  if (name === 'setup') {
    return <svg {...shared}><path d="M12 20V10M12 10 7 5M12 10l5-5M5 20h14" /><path d="M5 16v4M19 16v4" /></svg>;
  }
  if (name === 'analysis') {
    return <svg {...shared}><path d="M4 19.5h16M6.5 16V11M12 16V5M17.5 16V8" /><circle cx="6.5" cy="8" r="1" /><circle cx="17.5" cy="5" r="1" /></svg>;
  }
  if (name === 'climate') {
    return <svg {...shared}><path d="M7 18h10.5a3.5 3.5 0 0 0 .4-7 5.5 5.5 0 0 0-10.6-1.2A4.2 4.2 0 0 0 7 18Z" /><path d="M8 21h.01M12 21h.01M16 21h.01" /></svg>;
  }
  if (name === 'rotations') {
    return <svg {...shared}><path d="M20 7h-6l2.2-2.2M4 17h6l-2.2 2.2" /><path d="M18 7a7 7 0 0 0-12-2M6 17a7 7 0 0 0 12 2" /></svg>;
  }
  if (name === 'close') {
    return <svg {...shared}><path d="m6 6 12 12M18 6 6 18" /></svg>;
  }
  return <svg {...shared}><path d="M4 7h16M4 12h16M4 17h16" /></svg>;
}

function getFarmId(pathname: string): string | null {
  const match = pathname.match(/^\/plots\/([^/]+)(?:\/|$)/);
  if (!match || match[1] === 'new') return null;
  try {
    return decodeURIComponent(match[1]);
  } catch {
    return match[1];
  }
}

function getPageLabel(pathname: string): string {
  if (pathname === '/plots' || pathname === '/field') return 'My plots';
  if (pathname === '/plots/new') return 'Add a plot';
  if (pathname.endsWith('/edit')) return 'Edit plot';
  if (pathname.endsWith('/environment')) return 'Environmental context';
  if (pathname.endsWith('/recommendations') || pathname.startsWith('/comparison')) return 'Recommendations';
  if (pathname.startsWith('/plots/')) return 'Plot overview';
  return 'Workspace';
}

export default function Layout() {
  const { user, logout, error } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [logoutRequested, setLogoutRequested] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const isAuthPage = location.pathname === '/login' || location.pathname === '/signup';
  const isLoggingOut = logoutRequested && !user && !isAuthPage;
  const isDashboard = !isAuthPage && Boolean(user) && !isLoggingOut;
  const farmId = getFarmId(location.pathname);
  const farmPath = farmId ? `/plots/${encodeURIComponent(farmId)}` : null;
  const currentPageLabel = getPageLabel(location.pathname);

  useEffect(() => {
    if (!sidebarOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setSidebarOpen(false);
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [sidebarOpen]);

  const handleLogout = async () => {
    setLogoutRequested(true);
    try {
      await logout();
      navigate('/login', { replace: true });
    } catch {
      setLogoutRequested(false);
    }
  };

  const closeSidebar = () => setSidebarOpen(false);

  if (!isDashboard || !user) {
    return (
      <div className="app-shell">
        <main className="app-main auth-main">
          {error && !isAuthPage && <p className="alert alert-error layout-error" role="alert">{error}</p>}
          <Outlet />
        </main>
      </div>
    );
  }

  return (
    <div className="app-shell dashboard-shell">
      {sidebarOpen && (
        <button
          aria-label="Close navigation overlay"
          className="sidebar-backdrop"
          onClick={closeSidebar}
          type="button"
        />
      )}

      <aside className={`app-sidebar${sidebarOpen ? ' sidebar-open' : ''}`} id="primary-sidebar" aria-label="Primary navigation">
        <Link to="/plots" className="brand-mark sidebar-brand" aria-label="NovaYield home" onClick={closeSidebar}>
          <span className="brand-seal" aria-hidden="true">N</span>
          <span>NovaYield</span>
        </Link>

        <nav className="sidebar-navigation" aria-label="Dashboard sections">
          <div className="sidebar-group">
            <p className="sidebar-group-label">Workspace</p>
            <NavLink
              end
              to="/plots"
              className={({ isActive }) => `sidebar-link${isActive ? ' sidebar-link-active' : ''}`}
              onClick={closeSidebar}
            >
              <SidebarIcon name="plots" />
              <span>My plots</span>
            </NavLink>
            <NavLink
              end
              to="/plots/new"
              className={({ isActive }) => `sidebar-link${isActive ? ' sidebar-link-active' : ''}`}
              onClick={closeSidebar}
            >
              <SidebarIcon name="setup" />
              <span>Add a plot</span>
            </NavLink>
          </div>

          {farmPath && (
            <div className="sidebar-group">
              <p className="sidebar-group-label">Selected plot</p>
              <NavLink
                end
                to={farmPath}
                className={({ isActive }) => `sidebar-link${isActive ? ' sidebar-link-active' : ''}`}
                onClick={closeSidebar}
              >
                <SidebarIcon name="analysis" />
                <span>Plot overview</span>
              </NavLink>
              <NavLink
                end
                to={`${farmPath}/environment`}
                className={({ isActive }) => `sidebar-link${isActive ? ' sidebar-link-active' : ''}`}
                onClick={closeSidebar}
              >
                <SidebarIcon name="climate" />
                <span>Environmental context</span>
              </NavLink>
              <NavLink
                end
                to={`${farmPath}/recommendations`}
                className={({ isActive }) => `sidebar-link${isActive ? ' sidebar-link-active' : ''}`}
                onClick={closeSidebar}
              >
                <SidebarIcon name="rotations" />
                <span>Recommendations</span>
              </NavLink>
              <NavLink
                end
                to={`${farmPath}/edit`}
                className={({ isActive }) => `sidebar-link${isActive ? ' sidebar-link-active' : ''}`}
                onClick={closeSidebar}
              >
                <SidebarIcon name="setup" />
                <span>Edit plot</span>
              </NavLink>
            </div>
          )}
        </nav>

        <div className="sidebar-account">
          <div className="sidebar-user">
            <span className="user-avatar" aria-hidden="true">{user.email.slice(0, 1).toUpperCase()}</span>
            <span className="sidebar-user-copy">
              <span className="sidebar-user-label">Signed in as</span>
              <span className="sidebar-user-email" title={user.email}>{user.email}</span>
            </span>
          </div>
          <button onClick={handleLogout} className="logout-btn sidebar-logout" type="button" disabled={logoutRequested}>
            {logoutRequested ? 'Logging out…' : 'Log out'}
          </button>
        </div>
      </aside>

      <div className="dashboard-main-column">
        <header className="dashboard-topbar">
          <button
            aria-controls="primary-sidebar"
            aria-expanded={sidebarOpen}
            aria-label={sidebarOpen ? 'Close navigation menu' : 'Open navigation menu'}
            className="menu-toggle"
            onClick={() => setSidebarOpen((open) => !open)}
            type="button"
          >
            <SidebarIcon name={sidebarOpen ? 'close' : 'menu'} />
          </button>
          <div className="breadcrumbs" aria-label="Breadcrumb">
            <span>Workspace</span>
            <span aria-hidden="true">/</span>
            <strong>{currentPageLabel}</strong>
          </div>
          <span className="topbar-context">Agricultural decision support</span>
        </header>

        <main className="dashboard-content">
          {error && <p className="alert alert-error layout-error" role="alert">{error}</p>}
          <Outlet />
        </main>

        <footer className="app-footer">
          <span>NovaYield · Agricultural decision support</span>
          <span>Historical climate context · Relative rotation options</span>
        </footer>
      </div>
    </div>
  );
}
