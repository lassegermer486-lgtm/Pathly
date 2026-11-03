import Link from "next/link";
import { ArrowRightIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// Marken-CTA: dunkelgrüne Pille mit Pfeil im Signalgrün-Kreis;
// beim Hovern wächst der Kreis leicht und der Pfeil gleitet nach rechts.
export function CtaButton({
  href,
  children,
  className,
}: {
  href: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <Button
      size="lg"
      className={cn(
        "group/cta h-11 gap-3 rounded-full pr-1.5 pl-5 text-[0.95rem] hover:bg-primary",
        className
      )}
      nativeButton={false}
      render={<Link href={href} />}
    >
      {children}
      <span
        aria-hidden
        className="grid size-8 place-items-center overflow-hidden rounded-full bg-brand-green transition-transform duration-300 ease-out group-hover/cta:scale-110"
      >
        <ArrowRightIcon className="size-4 text-primary transition-transform duration-300 ease-out group-hover/cta:translate-x-0.5" />
      </span>
    </Button>
  );
}
