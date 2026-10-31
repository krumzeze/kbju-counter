import { type ReactNode, useState } from "react";

/** Illustration from /art/<name>.webp; shows the fallback until the file exists. */
export function Art({
  name,
  fallback = null,
  className = "art",
}: {
  name: string;
  fallback?: ReactNode;
  className?: string;
}) {
  const [missing, setMissing] = useState(false);
  if (missing) return <>{fallback}</>;
  return (
    <img
      className={className}
      src={`/art/${name}.webp`}
      alt=""
      loading="lazy"
      onError={() => setMissing(true)}
    />
  );
}
