import { useState, FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { Mail, Lock, Eye, EyeOff, AlertCircle } from 'lucide-react';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { authenticateEmployee, saveSession } from '../../services/auth';

export function LoginForm() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const [errors, setErrors] = useState<{ email?: string; password?: string; general?: string }>({});

  const validate = (): boolean => {
    const newErrors: { email?: string; password?: string; general?: string } = {};

    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      newErrors.email = 'Work email is required';
    } else {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(trimmedEmail)) {
        newErrors.email = 'Please enter a valid work email address';
      }
    }

    if (!password) {
      newErrors.password = 'Password is required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setErrors({});

    if (!validate()) {
      return;
    }

    setIsLoading(true);
    try {
      const result = await authenticateEmployee({
        email: email.trim(),
        password,
        rememberMe,
      });

      if (result.success && result.user) {
        saveSession({ user: result.user, token: result.token ?? '' });
        navigate('/app/dashboard', { replace: true });
      } else {
        setErrors({
          general: result.error || 'Unable to sign in. Please check your credentials and try again.',
        });
      }
    } catch {
      setErrors({
        general: 'Unable to sign in. Please check your credentials and try again.',
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="w-full space-y-5" noValidate>
      {errors.general && (
        <div
          role="alert"
          className="flex items-center gap-2.5 rounded-lg border border-destructive/20 bg-destructive/10 p-3.5 text-xs font-medium text-destructive"
        >
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{errors.general}</span>
        </div>
      )}

      {/* Work Email Field */}
      <div className="space-y-1.5">
        <label htmlFor="email" className="block text-xs font-semibold text-espresso tracking-tight">
          Work Email
        </label>
        <Input
          id="email"
          type="email"
          name="email"
          autoComplete="email"
          placeholder="employee@carrier.com"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
            if (errors.email) setErrors((prev) => ({ ...prev, email: undefined }));
          }}
          leftIcon={<Mail className="h-4 w-4 text-caramel/80" />}
          error={errors.email}
          disabled={isLoading}
        />
      </div>

      {/* Password Field */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <label htmlFor="password" className="block text-xs font-semibold text-espresso tracking-tight">
            Password
          </label>
          <a
            href="#forgot-password"
            onClick={(e) => {
              e.preventDefault();
              setErrors((prev) => ({
                ...prev,
                general: 'Password reset is managed via your enterprise identity provider.',
              }));
            }}
            className="text-xs font-medium text-caramel hover:text-espresso hover:underline transition-colors"
          >
            Forgot password?
          </a>
        </div>
        <Input
          id="password"
          type={showPassword ? 'text' : 'password'}
          name="password"
          autoComplete="current-password"
          placeholder="Enter your password"
          value={password}
          onChange={(e) => {
            setPassword(e.target.value);
            if (errors.password) setErrors((prev) => ({ ...prev, password: undefined }));
          }}
          leftIcon={<Lock className="h-4 w-4 text-caramel/80" />}
          rightIcon={
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              aria-label={showPassword ? 'Hide password' : 'Show password'}
              className="text-muted-foreground hover:text-espresso transition-colors p-1"
              tabIndex={-1}
            >
              {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          }
          error={errors.password}
          disabled={isLoading}
        />
      </div>

      {/* Remember Option */}
      <div className="flex items-center justify-between pt-0.5">
        <label className="flex items-center gap-2 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={rememberMe}
            onChange={(e) => setRememberMe(e.target.checked)}
            disabled={isLoading}
            className="h-4 w-4 rounded border-border text-primary focus:ring-accent focus:ring-offset-1 accent-primary"
          />
          <span className="text-xs text-muted-foreground">Remember this device</span>
        </label>
      </div>

      {/* Primary Sign In Button */}
      <Button
        type="submit"
        variant="primary"
        size="lg"
        isLoading={isLoading}
        className="w-full text-sm font-semibold tracking-wide"
      >
        {isLoading ? 'Signing in...' : 'Sign In'}
      </Button>

      {/* Security & Audit Compliance Disclosure */}
      <div className="pt-2 text-center">
        <p className="text-[11px] text-muted-foreground leading-normal">
          Authorized insurance personnel only. Access is secured and audited for compliance.
        </p>
      </div>
    </form>
  );
}
