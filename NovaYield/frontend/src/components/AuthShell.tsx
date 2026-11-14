import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { CheckIcon, LogoMark } from './icons';

interface AuthShellProps {
  title: string;
  subtitle: string;
  children: ReactNode;
  footer: ReactNode;
  asideTitle: string;
  asideText: string;
  asidePoints?: string[];
}

export default function AuthShell({
  title,
  subtitle,
  children,
  footer,
  asideTitle,
  asideText,
  asidePoints,
}: AuthShellProps) {
  return (
    <div className="auth">
      <div className="auth-form-side">
        <Link to="/" className="brand auth-brand">
          <LogoMark />
          NovaYield
        </Link>
        <div className="auth-center">
          <div className="auth-card">
            <div className="auth-head">
              <h1>{title}</h1>
              <p>{subtitle}</p>
            </div>
            {children}
            <p className="auth-switch">{footer}</p>
          </div>
        </div>
      </div>

      <aside className="auth-aside" aria-label="About NovaYield">
        <h2>{asideTitle}</h2>
        <p>{asideText}</p>
        {asidePoints && (
          <ul className="auth-points">
            {asidePoints.map((point) => (
              <li key={point}><CheckIcon />{point}</li>
            ))}
          </ul>
        )}
      </aside>
    </div>
  );
}
