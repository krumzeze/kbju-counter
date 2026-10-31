export function Logo({ size = 40 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden className="logo">
      <circle cx="32" cy="32" r="17" fill="none" stroke="var(--sage-deep)" strokeWidth="2.5" />
      <path
        d="M34.95 15.26A17 17 0 0 1 48.74 34.95M29.05 48.74A17 17 0 0 1 15.26 29.05"
        fill="none"
        stroke="var(--ink)"
        strokeWidth="4.5"
        strokeLinecap="round"
      />
      <circle cx="32" cy="32" r="6" fill="var(--sage-deep)" />
    </svg>
  );
}
