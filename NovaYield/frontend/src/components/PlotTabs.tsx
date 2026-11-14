import { NavLink } from 'react-router-dom';

export default function PlotTabs({ farmId }: { farmId: string }) {
  const base = `/plots/${encodeURIComponent(farmId)}`;
  const tabClass = ({ isActive }: { isActive: boolean }) => `tab${isActive ? ' active' : ''}`;
  return (
    <nav className="tabs" aria-label="Plot sections">
      <NavLink end to={base} className={tabClass}>Overview</NavLink>
      <NavLink end to={`${base}/environment`} className={tabClass}>Climate</NavLink>
      <NavLink end to={`${base}/recommendations`} className={tabClass}>Recommendations</NavLink>
    </nav>
  );
}
