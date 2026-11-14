import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../context/auth-context';
import LoadingState from './common/LoadingState';

export default function ProtectedRoute() {
  const { user, isInitialized } = useAuth();

  if (!isInitialized) {
    return <LoadingState message="Checking your session…" />;
  }

  // Redirect to login if not authenticated
  if (!user) {
    return <Navigate to="/login" replace />;
  }

  // Render the protected child routes
  return <Outlet />;
}
