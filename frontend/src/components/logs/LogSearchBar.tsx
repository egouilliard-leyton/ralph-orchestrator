"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SearchIcon, ClearIcon } from "@/components/ui/icons";

interface LogSearchBarProps {
  searchInput: string;
  onSearchInputChange: (value: string) => void;
  onSearch: (e: React.FormEvent) => void;
  onClear: () => void;
}

export function LogSearchBar({
  searchInput,
  onSearchInputChange,
  onSearch,
  onClear,
}: LogSearchBarProps) {
  return (
    <form onSubmit={onSearch} className="flex gap-2">
      <div className="relative flex-1">
        <SearchIcon className="absolute left-2 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
        <Input
          placeholder="Search logs..."
          value={searchInput}
          onChange={(e) => onSearchInputChange(e.target.value)}
          className="pl-8 pr-8 h-8"
        />
        {searchInput && (
          <Button
            type="button"
            variant="ghost"
            size="icon-xs"
            className="absolute right-1 top-1/2 -translate-y-1/2"
            onClick={onClear}
          >
            <ClearIcon className="size-3" />
          </Button>
        )}
      </div>
      <Button type="submit" size="sm" variant="outline">
        Search
      </Button>
    </form>
  );
}
