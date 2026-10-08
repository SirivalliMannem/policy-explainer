import { LoginHero } from '../components/auth/LoginHero';
import { LoginCard } from '../components/auth/LoginCard';

export function LoginPage() {
  return (
    <div className="w-full min-h-screen lg:h-screen lg:max-h-screen w-screen max-w-[100vw] bg-[#F8FAFC] font-sans text-[#0F2A43] grid grid-cols-1 lg:grid-cols-[60%_40%] overflow-x-hidden overflow-y-auto lg:overflow-hidden">
      <LoginHero />
      <main className="flex items-center justify-center h-full w-full bg-[#F8FAFC] p-4 sm:p-6 lg:p-8 xl:p-12 overflow-y-auto lg:overflow-hidden">
        <LoginCard />
      </main>
    </div>
  );
}

export default LoginPage;
