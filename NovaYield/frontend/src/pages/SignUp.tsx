import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/auth-context';

export default function SignUp() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  
  const { signup, isLoading, error } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLocalError(null);

    if (password !== confirmPassword) {
      setLocalError('Passwords do not match.');
      return;
    }

    try {
      await signup(email, password);
      navigate('/plots');
    } catch {
      // Error handled by context
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-left">
        <div className="auth-container">
          <Link to="/" className="auth-logo">
            NovaYield
          </Link>

          <div className="auth-header">
            <h1>Create account</h1>
            <p>Join NovaYield to start optimizing your fields.</p>
          </div>

          {(error || localError) && (
            <p className="alert alert-error auth-error" role="alert">
              {localError || error}
            </p>
          )}
          
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

            <div className="form-group">
              <label htmlFor="confirm-password">Confirm Password</label>
              <input 
                id="confirm-password"
                type="password" 
                value={confirmPassword} 
                onChange={e => setConfirmPassword(e.target.value)} 
                className="form-input"
                placeholder="Confirm Password"
                required 
              />
            </div>

            <button type="submit" className="submit-btn auth-submit" disabled={isLoading}>
              {isLoading ? 'Creating account…' : 'Create account'}
            </button>
          </form>
          
          <div className="auth-footer">
            Already have an account? <Link to="/login" className="nav-link auth-inline-link">Log in</Link>
          </div>
        </div>
      </div>

      <div className="auth-right">
        <div className="brand-display">
          <p className="kicker">Field-aware decision support</p>
          <h2>NovaYield</h2>
          <p>Start with your plot’s history. NovaYield adds regional climate context and explains the trade-offs behind each rotation.</p>
          <ul className="auth-points">
            <li><strong>One plot at a time</strong><span>Keep each decision plot and its crop events organized.</span></li>
            <li><strong>Historical context</strong><span>Use stored NASA POWER observations, not a weather forecast.</span></li>
            <li><strong>Clear comparisons</strong><span>See relative criteria, planting windows, and key assumptions.</span></li>
          </ul>
        </div>
      </div>
    </div>
  );
}
