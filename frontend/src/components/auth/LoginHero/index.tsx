import { Brand } from './Brand';
import { HeroStatement } from './HeroStatement';
import { AnimatedQuestion } from './AnimatedQuestion';
import { HeroValues } from './HeroValues';
import { HeroFooter } from './HeroFooter';

export function LoginHero() {
  return (
    <section className="relative overflow-hidden bg-[#0F2A43] text-[#f1f5f9] px-7 sm:px-12 lg:px-16 py-8 sm:py-10 flex flex-col justify-between h-full max-h-screen">
      {/* Animated dotted radial grid */}
      <div
        className="absolute -inset-[30px] pointer-events-none animate-grid-drift opacity-80"
        style={{
          backgroundImage: 'radial-gradient(rgba(249,115,22,0.22) 1.2px, transparent 1.2px)',
          backgroundSize: '26px 26px',
        }}
        aria-hidden="true"
      />

      {/* Floating blurred atmospheric orange glow */}
      <div
        className="absolute w-[440px] h-[440px] rounded-full bg-[#F97316] blur-[130px] opacity-[0.24] -right-[120px] bottom-[30px] pointer-events-none animate-glow-drift"
        aria-hidden="true"
      />

      {/* TOP: Brand Identity */}
      <div className="relative z-10 shrink-0">
        <Brand />
      </div>

      {/* MIDDLE: Hero Statement & Supporting Description */}
      <div className="relative z-10 my-auto py-4 sm:py-6 max-w-[640px]">
        <HeroStatement />
      </div>

      {/* BOTTOM: Animated Question Pill & Version Footer */}
      <div className="relative z-10 shrink-0 pt-3 space-y-4">
        <AnimatedQuestion />
        <HeroValues />
        <HeroFooter />
      </div>
    </section>
  );
}

export default LoginHero;
