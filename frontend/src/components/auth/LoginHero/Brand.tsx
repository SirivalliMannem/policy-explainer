import { Shield } from 'lucide-react';

export function Brand() {
  return (
    <div className="flex items-center gap-3.5">
      <div className="w-[54px] h-[54px] border border-[#F97316] rounded-xl grid place-items-center bg-[#16385a] animate-logo-pulse shrink-0">
        <Shield className="w-6 h-6 text-[#F97316] fill-[#F97316]/20" strokeWidth={2.2} />
      </div>
      <div>
        <b className="font-serif font-bold text-[28px] text-white block leading-tight tracking-normal">
          Policy Explainer
        </b>
        <small className="text-[#F97316] tracking-[0.09em] text-[14px] font-sans font-semibold block uppercase">
          ENTERPRISE POLICY INTELLIGENCE
        </small>
      </div>
    </div>
  );
}

export default Brand;
