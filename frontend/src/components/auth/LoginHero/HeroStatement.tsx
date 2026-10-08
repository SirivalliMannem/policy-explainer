export function HeroStatement() {
  return (
    <div className="space-y-4 sm:space-y-5">
      <h1 className="font-serif font-bold text-[34px] sm:text-[40px] lg:text-[46px] xl:text-[52px] leading-[1.08] text-white tracking-normal">
        <span className="block overflow-hidden pb-0.5">
          <span className="block translate-y-[110%] animate-hero-slide-up [animation-delay:0s]">
            One platform.
          </span>
        </span>
        <span className="block overflow-hidden pb-0.5">
          <span className="block translate-y-[110%] animate-hero-slide-up [animation-delay:0.12s]">
            Every policy.
          </span>
        </span>
        <span className="block overflow-hidden pt-1.5 sm:pt-2 pb-1">
          <span className="block translate-y-[110%] animate-hero-slide-up [animation-delay:0.26s]">
            <span className="animated-orange-text">
              One conversation,
            </span>
          </span>
        </span>
        <span className="block overflow-hidden pb-1">
          <span className="block translate-y-[110%] animate-hero-slide-up [animation-delay:0.38s]">
            <span className="animated-orange-text">
              connected.
            </span>
          </span>
        </span>
      </h1>

      <p className="text-[15px] sm:text-[16px] lg:text-[17px] leading-[1.6] text-[#cbd5e1] max-w-[500px] opacity-0 animate-fade-in [animation-delay:0.7s] [animation-fill-mode:forwards] font-sans pt-1">
        Policy intelligence that brings coverage, forms, exclusions, and supporting evidence together.
      </p>
    </div>
  );
}

export default HeroStatement;
