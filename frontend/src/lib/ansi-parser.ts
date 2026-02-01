/**
 * ANSI escape code parser for terminal output rendering
 */

// ANSI foreground color code mappings to Tailwind classes
export const ANSI_COLORS: Record<number, string> = {
  30: "text-gray-900 dark:text-gray-100",
  31: "text-red-600 dark:text-red-400",
  32: "text-green-600 dark:text-green-400",
  33: "text-yellow-600 dark:text-yellow-400",
  34: "text-blue-600 dark:text-blue-400",
  35: "text-purple-600 dark:text-purple-400",
  36: "text-cyan-600 dark:text-cyan-400",
  37: "text-gray-200 dark:text-gray-300",
  90: "text-gray-500",
  91: "text-red-400",
  92: "text-green-400",
  93: "text-yellow-400",
  94: "text-blue-400",
  95: "text-purple-400",
  96: "text-cyan-400",
  97: "text-white",
};

// ANSI background color code mappings to Tailwind classes
export const ANSI_BG_COLORS: Record<number, string> = {
  40: "bg-gray-900",
  41: "bg-red-600",
  42: "bg-green-600",
  43: "bg-yellow-600",
  44: "bg-blue-600",
  45: "bg-purple-600",
  46: "bg-cyan-600",
  47: "bg-gray-200",
};

export interface AnsiSegment {
  text: string;
  classes: string;
  isBold?: boolean;
  isUnderline?: boolean;
}

/**
 * Parse ANSI escape codes from text and return segments with styling information
 */
export function parseAnsiCodes(text: string): AnsiSegment[] {
  const segments: AnsiSegment[] = [];
  const ansiRegex = /\x1b\[([0-9;]*)m/g;

  let currentClasses: string[] = [];
  let isBold = false;
  let isUnderline = false;
  let lastIndex = 0;
  let match;

  while ((match = ansiRegex.exec(text)) !== null) {
    // Add text before this ANSI code
    if (match.index > lastIndex) {
      segments.push({
        text: text.substring(lastIndex, match.index),
        classes: currentClasses.join(" "),
        isBold,
        isUnderline,
      });
    }

    // Parse ANSI codes
    const codes = match[1]?.split(";").map(Number) ?? [0];
    for (const code of codes) {
      if (code === 0) {
        // Reset
        currentClasses = [];
        isBold = false;
        isUnderline = false;
      } else if (code === 1) {
        isBold = true;
      } else if (code === 4) {
        isUnderline = true;
      } else if (ANSI_COLORS[code]) {
        currentClasses = currentClasses.filter((c) => !c.startsWith("text-"));
        currentClasses.push(ANSI_COLORS[code]);
      } else if (ANSI_BG_COLORS[code]) {
        currentClasses = currentClasses.filter((c) => !c.startsWith("bg-"));
        currentClasses.push(ANSI_BG_COLORS[code]);
      }
    }

    lastIndex = match.index + match[0].length;
  }

  // Add remaining text
  if (lastIndex < text.length) {
    segments.push({
      text: text.substring(lastIndex),
      classes: currentClasses.join(" "),
      isBold,
      isUnderline,
    });
  }

  return segments;
}

/**
 * Strip all ANSI escape codes from text
 */
export function stripAnsiCodes(text: string): string {
  return text.replace(/\x1b\[[0-9;]*m/g, "");
}

/**
 * Escape special regex characters in a string
 */
export function escapeRegExp(string: string): string {
  return string.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
