import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import AuthShell from '../components/AuthShell';
import { AlertIcon, EyeIcon, EyeOffIcon } from '../components/icons';
import { useAuth } from '../context/auth-context';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const { login, isLoading, error } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await login(email, password);
      navigate('/plots');
    } catch {
      // Error handled by context
    }
  };

  return (
    <AuthShell
      title="Log in"
      subtitle="Welcome back. Enter your details to continue."
      footer={<>New to NovaYield? <Link to="/signup">Create an account</Link></>}
      asideTitle="Crop rotation grounded in your farm history and regional climate."
      asideText="Compare up to three explainable rotation options for each plot."
    >
      {error && <p className="alert alert-error" role="alert"><AlertIcon />{error}</p>}

      <form onSubmit={handleSubmit} className="auth-form">
        <div className="field">
          <label className="label" htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="input"
            placeholder="you@example.com"
            required
          />
        </div>

        <div className="field">
          <label className="label" htmlFor="password">Password</label>
          <div className="password-field">
            <input
              id="password"
              type={showPassword ? 'text' : 'password'}
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input"
              required
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="icon-btn"
              aria-label={showPassword ? 'Hide password' : 'Show password'}
              aria-pressed={showPassword}
            >
              {showPassword ? <EyeOffIcon /> : <EyeIcon />}
            </button>
          </div>
        </div>

        <button type="submit" className="btn btn-primary btn-block" disabled={isLoading}>
          {isLoading ? 'Logging in…' : 'Log in'}
        </button>
      </form>
    </AuthShell>
  );
}
