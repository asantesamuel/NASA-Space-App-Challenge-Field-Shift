import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import AuthShell from '../components/AuthShell';
import { AlertIcon, EyeIcon, EyeOffIcon } from '../components/icons';
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

  const message = localError || error;

  return (
    <AuthShell
      title="Create your account"
      subtitle="Set up your plots and compare rotation options."
      footer={<>Already have an account? <Link to="/login">Log in</Link></>}
      asideTitle="Start with your plot’s history."
      asideText="NovaYield adds regional climate context and explains the trade-offs behind each rotation."
      asidePoints={[
        'Keep each plot and its crop events organised in one place.',
        'Uses stored NASA POWER observations, not a weather forecast.',
        'See relative criteria, planting windows, and key assumptions.',
      ]}
    >
      {message && <p className="alert alert-error" role="alert"><AlertIcon />{message}</p>}

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
              autoComplete="new-password"
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

        <div className="field">
          <label className="label" htmlFor="confirm-password">Confirm password</label>
          <input
            id="confirm-password"
            type={showPassword ? 'text' : 'password'}
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="input"
            required
          />
        </div>

        <button type="submit" className="btn btn-primary btn-block" disabled={isLoading}>
          {isLoading ? 'Creating account…' : 'Create account'}
        </button>
      </form>
    </AuthShell>
  );
}
