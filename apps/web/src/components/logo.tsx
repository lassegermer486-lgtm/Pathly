import Image from "next/image";
import Link from "next/link";
import { cn } from "@/lib/utils";

// Wortmarke aus dem Original-Logo (docs/brand/pathly-logo-original.png),
// erzeugt mit scripts/build-brand-assets.py. `variant="white"` für dunkle Flächen.
export function Logo({
  className,
  variant = "default",
}: {
  className?: string;
  variant?: "default" | "white";
}) {
  return (
    <Link href="/" aria-label="Pathly – zur Startseite" className={cn("inline-flex shrink-0", className)}>
      <Image
        src={variant === "white" ? "/brand/pathly-logo-white.png" : "/brand/pathly-logo.png"}
        alt="pathly"
        width={681}
        height={225}
        priority
        className="h-8 w-auto"
      />
    </Link>
  );
}
