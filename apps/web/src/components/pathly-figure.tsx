import Image from "next/image";
import { cn } from "@/lib/utils";

const WIDTH = 511;
const HEIGHT = 900;
export const PATHLY_FIGURE_RATIO = WIDTH / HEIGHT;

// Die Pathly-Figur mit Absolventenhut (3D-Modell, siehe docs/brand/figur).
// Größe über die Klasse setzen, z. B. <PathlyFigure className="h-40" sizes="100px" />.
// Mit `title` wird sie für Screenreader benannt, ohne gilt sie als Dekoration.
export function PathlyFigure({
  title,
  sizes = "200px",
  className,
}: {
  title?: string;
  sizes?: string;
  className?: string;
}) {
  return (
    <Image
      src="/images/figur/pathly-figur.webp"
      alt={title ?? ""}
      width={WIDTH}
      height={HEIGHT}
      sizes={sizes}
      className={cn("w-auto", className)}
    />
  );
}
