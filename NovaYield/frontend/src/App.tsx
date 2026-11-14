import { BrowserRouter, Routes, Route, Navigate, useSearchParams } from 'react-router-dom';
import Layout from './components/layout.tsx';
import ProtectedRoute from './components/ProtectedRoute'; 
import SignUp from './pages/SignUp';
import Login from './pages/Login';
import FieldSetup from './pages/FieldSetup';
import Comparison from './pages/Comparison';
import PlotList from './pages/PlotList';
import PlotDetails from './pages/PlotDetails';
import EnvironmentalContext from './pages/EnvironmentalContext';

function LegacyComparisonRedirect() {
  const [searchParams] = useSearchParams();
  const farmId = searchParams.get('farmId');
  return (
    <Navigate
      to={farmId ? `/plots/${encodeURIComponent(farmId)}/recommendations` : '/plots'}
      replace
    />
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Navigate to="/plots" replace />} />
          <Route path="/signup" element={<SignUp />} />
          <Route path="/login" element={<Login />} />

          {/* Protected Routes Wrapper */}
          <Route element={<ProtectedRoute />}>
            <Route path="/field" element={<Navigate to="/plots" replace />} />
            <Route path="/comparison" element={<LegacyComparisonRedirect />} />
            <Route path="/plots" element={<PlotList />} />
            <Route path="/plots/new" element={<FieldSetup />} />
            <Route path="/plots/:farmId" element={<PlotDetails />} />
            <Route path="/plots/:farmId/edit" element={<FieldSetup />} />
            <Route path="/plots/:farmId/environment" element={<EnvironmentalContext />} />
            <Route path="/plots/:farmId/recommendations" element={<Comparison />} />
          </Route>

          <Route path="*" element={<Navigate to="/plots" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
