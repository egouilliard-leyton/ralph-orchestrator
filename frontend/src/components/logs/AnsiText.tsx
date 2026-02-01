"use client";

import { useMemo } from "react";
import { cn } from "@/lib/utils";
import { parseAnsiCodes, escapeRegExp } from "@/lib/ansi-parser";

interface AnsiTextProps {
  text: string;
  searchTerm?: string;
}

export function AnsiText({ text, searchTerm }: AnsiTextProps) {
  const segments = useMemo(() => parseAnsiCodes(text), [text]);

  return (
    <>
      {segments.map((segment, index) => {
        let content: React.ReactNode = segment.text;

        // Highlight search term
        if (searchTerm && segment.text.toLowerCase().includes(searchTerm.toLowerCase())) {
          const parts = segment.text.split(new RegExp(`(${escapeRegExp(searchTerm)})`, "gi"));
          content = parts.map((part, i) =>
            part.toLowerCase() === searchTerm.toLowerCase() ? (
              <mark key={i} className="bg-yellow-300 dark:bg-yellow-600 text-inherit">
                {part}
              </mark>
            ) : (
              part
            )
          );
        }

        return (
          <span
            key={index}
            className={cn(
              segment.classes,
              segment.isBold && "font-bold",
              segment.isUnderline && "underline"
            )}
          >
            {content}
          </span>
        );
      })}
    </>
  );
}
