import { useEffect, useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/auth-context';
import { CloseIcon, LogoMark, LogoutIcon, MenuIcon, PlotsIcon, PlusIcon } from './icons';

function getPageLabel(pathname: string): string | null {
  if (pathname === '/plots' || pathname === '/field') return null;
  if (pathname === '/plots/new') return 'Add plot';
  if (pathname.endsWith('/edit')) return 'Edit plot';
  if (pathname.endsWith('/environment')) return 'Climate';
  if (pathname.endsWith('/recommendations') || pathname.startsWith('/comparison')) return 'Recommendations';
  if (pathname.startsWith('/plots/')) return 'Overview';
  return null;
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
  const pageLabel = getPageLabel(location.pathname);

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
  const navClass = ({ isActive }: { isActive: boolean }) => `nav-link${isActive ? ' active' : ''}`;

  if (!isDashboard || !user) {
    return (
      <>
        {error && !isAuthPage && <p className="alert alert-error layout-notice" role="alert">{error}</p>}
        <Outlet />
      </>
    );
  }

  return (
    <div className="app">
      {sidebarOpen && <button aria-label="Close navigation" className="scrim" onClick={closeSidebar} type="button" />}

      <aside className={`sidebar${sidebarOpen ? ' open' : ''}`} id="primary-sidebar" aria-label="Primary">
        <Link to="/plots" className="brand" aria-label="NovaYield home" onClick={closeSidebar}>
          <LogoMark />
          NovaYield
        </Link>

        <nav className="nav" aria-label="Main">
          <span className="nav-label">Workspace</span>
          <NavLink end to="/plots" className={navClass} onClick={closeSidebar}>
            <PlotsIcon /> My plots
          </NavLink>
          <NavLink end to="/plots/new" className={navClass} onClick={closeSidebar}>
            <PlusIcon /> Add plot
          </NavLink>
        </nav>

        <div className="sidebar-foot">
          <span className="avatar" aria-hidden="true">{user.email.slice(0, 1).toUpperCase()}</span>
          <span className="account">
            <span className="account-label">Signed in as</span>
            <span className="account-email" title={user.email}>{user.email}</span>
          </span>
          <button
            type="button"
            className="icon-btn"
            onClick={handleLogout}
            disabled={logoutRequested}
            aria-label={logoutRequested ? 'Logging out' : 'Log out'}
            title="Log out"
          >
            <LogoutIcon />
          </button>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <button
            aria-controls="primary-sidebar"
            aria-expanded={sidebarOpen}
            aria-label={sidebarOpen ? 'Close navigation' : 'Open navigation'}
            className="icon-btn menu-btn"
            onClick={() => setSidebarOpen((open) => !open)}
            type="button"
          >
            {sidebarOpen ? <CloseIcon /> : <MenuIcon />}
          </button>
          <nav className="crumbs" aria-label="Breadcrumb">
            {pageLabel ? (
              <>
                <Link to="/plots">My plots</Link>
                <span className="sep" aria-hidden="true">/</span>
                <span aria-current="page">{pageLabel}</span>
              </>
            ) : (
              <span aria-current="page">My plots</span>
            )}
          </nav>
        </header>

        <main className="content">
          {error && <p className="alert alert-error layout-notice" role="alert">{error}</p>}
          <Outlet />
        </main>

        <footer className="footer">
          <span>NovaYield · Crop rotation decision support</span>
          <span>Historical NASA POWER context · Relative, rule-based options</span>
        </footer>
      </div>
    </div>
  );
}
