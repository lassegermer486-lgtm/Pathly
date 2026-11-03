"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

// Baut Text Buchstabe für Buchstabe auf – sofort (onMount) oder sobald er ins Bild scrollt.
// `accent` hebt ein Wort in Markengrün hervor.
export function CharReveal({
  text,
  accent,
  as: Tag = "span",
  trigger = "mount",
  delay = 0,
  className,
}: {
  text: string;
  accent?: string;
  as?: "h1" | "h2" | "span";
  trigger?: "mount" | "view";
  delay?: number;
  className?: string;
}) {
  const ref = useRef<HTMLElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (trigger === "mount") {
      const frame = requestAnimationFrame(() => setVisible(true));
      return () => cancelAnimationFrame(frame);
    }
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          io.disconnect();
        }
      },
      { threshold: 0.4 }
    );
    io.observe(el);
    return () => io.disconnect();
  }, [trigger]);

  const accentStart = accent ? text.indexOf(accent) : -1;
  let index = 0;

  return (
    <Tag ref={ref as never} className={className} aria-label={text}>
      {text.split(" ").map((word, w, all) => {
        const wordStart = all.slice(0, w).join(" ").length + (w > 0 ? 1 : 0);
        const isAccent =
          accentStart >= 0 && wordStart >= accentStart && wordStart < accentStart + accent!.length;
        return (
          <span key={w} aria-hidden className={cn("inline-block whitespace-nowrap", isAccent && "text-brand-green")}>
            {[...word].map((char) => {
              const i = index++;
              return (
                <span
                  key={i}
                  className="inline-block transition-[opacity,transform,filter] duration-700 ease-out motion-reduce:transition-none"
                  style={{
                    transitionDelay: `${delay + i * 22}ms`,
                    opacity: visible ? 1 : 0,
                    transform: visible ? "none" : "translateY(0.35em)",
                    filter: visible ? "none" : "blur(4px)",
                  }}
                >
                  {char}
                </span>
              );
            })}
            {w < all.length - 1 && " "}
          </span>
        );
      })}
    </Tag>
  );
}
