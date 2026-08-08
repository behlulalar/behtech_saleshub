interface Props {
  className?: string;
  showTagline?: boolean;
}

export default function BrandLogo({ className = 'h-10', showTagline = false }: Props) {
  return (
    <div>
      <img
        src="/behtech-logo.png"
        alt="BehTech Sales Hub"
        className={`w-auto object-contain object-left ${className}`}
      />
      {showTagline && (
        <p className="mt-1 text-[10px] font-semibold uppercase tracking-[0.15em] text-brand-500">
          Beyond The Code
        </p>
      )}
    </div>
  );
}
