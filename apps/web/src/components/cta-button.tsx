import Link from "next/link";
import { ArrowRightIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// Marken-CTA: dunkelgrüne Pille mit grünem Punkt, der beim Hovern zum Pfeil-Kreis wächst.
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
        "group/cta h-11 gap-3 rounded-full pr-2 pl-5 text-[0.95rem] hover:bg-primary",
        className
      )}
      nativeButton={false}
      render={<Link href={href} />}
    >
      {children}
      <span
        aria-hidden
        className="grid size-7 place-items-center rounded-full transition-colors duration-300 group-hover/cta:bg-brand-green"
      >
        <span className="size-2.5 rounded-full bg-brand-green transition-all duration-300 [grid-area:1/1] group-hover/cta:size-0" />
        <ArrowRightIcon className="size-0 text-primary transition-all duration-300 [grid-area:1/1] group-hover/cta:size-4" />
      </span>
    </Button>
  );
}
