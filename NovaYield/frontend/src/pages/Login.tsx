import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
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
    <div className="auth-page login-page">
      <div className="auth-left">
        <div className="auth-container">
          <Link to="/" className="auth-logo">
            NovaYield
          </Link>

          <div className="auth-header">
            <h1>Log in</h1>
            <p>Welcome back! Please enter your details.</p>
          </div>

          {error && <p className="alert alert-error auth-error" role="alert">{error}</p>}

          <form onSubmit={handleSubmit} className="form-grid auth-form">
            <div className="form-group">
              <label htmlFor="email">Email</label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                className="form-input"
                placeholder="Your Email"
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="password">Password</label>
              <div className="password-field">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  className="form-input"
                  placeholder="Password"
                  aria-describedby="password-visibility-hint"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="password-toggle"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  aria-pressed={showPassword}
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                    <circle cx="12" cy="12" r="3"></circle>
                  </svg>
                </button>
              </div>
              <small id="password-visibility-hint">Use the eye control to show or hide your password.</small>
            </div>

            <button type="submit" className="submit-btn auth-submit" disabled={isLoading}>
              {isLoading ? 'Logging in…' : 'Log in'}
            </button>
          </form>

          <div className="auth-footer">
            Don’t have an account? <Link to="/signup" className="nav-link auth-inline-link">Create an account</Link>
          </div>
        </div>
      </div>

      <div className="auth-right">
        <div className="brand-display">
          <p className="kicker">Agricultural decision support</p>
          <h2>NovaYield</h2>
          <p>Crop rotation, grounded in your farm history and regional climate.</p>
        </div>
      </div>
    </div>
  );
}
