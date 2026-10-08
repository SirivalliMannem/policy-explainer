import { useState, FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { Eye, EyeOff, AlertCircle } from 'lucide-react';
import { authenticateEmployee } from '../../services/auth';

export function LoginCard() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('manager@feuji.com');
  const [password, setPassword] = useState('••••••••••••');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      setError('Please enter your work email.');
      return;
    }

    if (!password) {
      setError('Please enter your password.');
      return;
    }

    setIsLoading(true);
    try {
      const result = await authenticateEmployee({
        email: trimmedEmail,
        password,
      });

      if (result.success) {
        navigate('/app/dashboard');
      } else {
        setError(result.error || 'Unable to sign in. Please verify your credentials.');
      }
    } catch {
      setError('Unable to sign in. Please verify your connection and try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="w-full max-w-[450px] mx-auto animate-card-enter">
      <div className="bg-card border border-[#e2e8f0] rounded-[20px] p-6 sm:p-8 lg:p-9 shadow-[0_4px_24px_rgba(15,42,67,0.06)]">
        <h2 className="font-sans font-bold text-[26px] sm:text-[30px] text-[#0F2A43] mb-1.5 leading-tight tracking-tight">
          Welcome back
        </h2>
        <p className="text-[#64748b] text-[15px] sm:text-[16px] mb-5 sm:mb-6 font-sans">
          Sign in to continue to Policy Explainer.
        </p>

        {error && (
          <div
            role="alert"
            className="flex items-center gap-2 rounded-lg border border-destructive/20 bg-destructive/10 p-3 mb-4 text-xs font-medium text-destructive"
          >
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate>
          {/* Work Email */}
          <div>
            <label
              htmlFor="email-input"
              className="font-semibold text-[14px] sm:text-[15px] block text-[#0F2A43] mb-1.5 font-sans"
            >
              Work Email
            </label>
            <input
              id="email-input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="manager@feuji.com"
              disabled={isLoading}
              className="w-full py-2.5 sm:py-3 px-3.5 sm:px-4 border border-[#cbd5e1] rounded-[10px] bg-[#FFF7ED] text-[15px] sm:text-[16px] text-[#0F2A43] font-sans transition-all focus:border-[#F97316] focus:ring-2 focus:ring-[#F97316]/20 focus:outline-none"
            />
          </div>

          {/* Password */}
          <div className="mt-3.5 sm:mt-4">
            <label
              htmlFor="password-input"
              className="font-semibold text-[14px] sm:text-[15px] block text-[#0F2A43] mb-1.5 font-sans"
            >
              Password
            </label>
            <div className="relative">
              <input
                id="password-input"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter password"
                disabled={isLoading}
                className="w-full py-2.5 sm:py-3 px-3.5 sm:px-4 pr-11 border border-[#cbd5e1] rounded-[10px] bg-[#FFF7ED] text-[15px] sm:text-[16px] text-[#0F2A43] font-sans transition-all focus:border-[#F97316] focus:ring-2 focus:ring-[#F97316]/20 focus:outline-none"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[#64748b] hover:text-[#0F2A43] p-1.5 transition-colors"
                tabIndex={-1}
              >
                {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
              </button>
            </div>
          </div>

          {/* Sign In Button */}
          <button
            type="submit"
            disabled={isLoading}
            className="mt-5 sm:mt-6 w-full py-3 sm:py-3.5 border-0 rounded-[10px] bg-[#EA580C] hover:bg-[#C2410C] text-white text-[16px] sm:text-[17px] font-semibold transition-all hover:-translate-y-0.5 hover:shadow-[0_8px_20px_rgba(234,88,12,0.3)] active:translate-y-0 cursor-pointer disabled:opacity-70 disabled:cursor-not-allowed"
          >
            {isLoading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  );
}

export default LoginCard;
