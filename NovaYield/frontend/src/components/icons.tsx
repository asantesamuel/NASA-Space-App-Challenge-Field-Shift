import type { SVGProps } from 'react';

const base = {
  'aria-hidden': true as const,
  className: 'icon',
  fill: 'none',
  stroke: 'currentColor',
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  strokeWidth: 1.75,
  viewBox: '0 0 24 24',
};

type IconProps = SVGProps<SVGSVGElement>;

export function LogoMark({ className = 'brand-mark' }: { className?: string }) {
  return (
    <svg aria-hidden="true" className={className} viewBox="0 0 24 24" fill="none">
      <rect x="2" y="2" width="20" height="20" rx="6" fill="currentColor" />
      <path d="M7 16.5V10m5 6.5V7.5m5 9V12" stroke="#fff" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export const PlotsIcon = (p: IconProps) => (
  <svg {...base} {...p}><rect x="3.5" y="4" width="17" height="16" rx="2" /><path d="M3.5 10h17M9.5 10v10" /></svg>
);
export const PlusIcon = (p: IconProps) => (
  <svg {...base} {...p}><path d="M12 5v14M5 12h14" /></svg>
);
export const LogoutIcon = (p: IconProps) => (
  <svg {...base} {...p}><path d="M9 20H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h3M16 16l4-4-4-4M20 12H9" /></svg>
);
export const MenuIcon = (p: IconProps) => (
  <svg {...base} {...p}><path d="M4 7h16M4 12h16M4 17h16" /></svg>
);
export const CloseIcon = (p: IconProps) => (
  <svg {...base} {...p}><path d="m6 6 12 12M18 6 6 18" /></svg>
);
export const EyeIcon = (p: IconProps) => (
  <svg {...base} {...p}><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z" /><circle cx="12" cy="12" r="3" /></svg>
);
export const EyeOffIcon = (p: IconProps) => (
  <svg {...base} {...p}><path d="M10.7 5.1A10 10 0 0 1 12 5c6.4 0 10 7 10 7a17 17 0 0 1-3.2 4M6.6 6.6A17 17 0 0 0 2 12s3.6 7 10 7a9.700 9.700 0 0 0 5.400-1.600M3 3l18 18M9.900 9.900a3 3 0 0 0 4.200 4.200" /></svg>
);
export const InfoIcon = (p: IconProps) => (
  <svg {...base} {...p}><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></svg>
);
export const AlertIcon = (p: IconProps) => (
  <svg {...base} {...p}><path d="M10.300 3.900 2.400 17.500A2 2 0 0 0 4.100 20.500h15.800a2 2 0 0 0 1.700-3L13.700 3.900a2 2 0 0 0-3.400 0Z" /><path d="M12 9v4M12 17h.01" /></svg>
);
export const CheckIcon = (p: IconProps) => (
  <svg {...base} {...p}><path d="m5 12.500 4.500 4.500L19 7.500" /></svg>
);
export const ArrowLeftIcon = (p: IconProps) => (
  <svg {...base} {...p}><path d="M19 12H5M11 6l-6 6 6 6" /></svg>
);
export const RefreshIcon = (p: IconProps) => (
  <svg {...base} {...p}><path d="M20 11a8 8 0 0 0-14.500-4.300M4 5v4h4M4 13a8 8 0 0 0 14.500 4.300M20 19v-4h-4" /></svg>
);
export const SproutIcon = (p: IconProps) => (
  <svg {...base} {...p}><path d="M12 21v-9M12 12C12 8 9.500 6 5 6c0 4 2.500 6 7 6ZM12 14c0-3 2-5 7-5 0 3.500-2 5-7 5Z" /></svg>
);
