import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import { Fragment, useMemo, useState, type ReactNode } from "react";
import { Empty } from "@/components/page";
import { Button } from "@/components/ui/button";
import { Input, NativeSelect } from "@/components/ui/input";
import { cn } from "@/lib/utils";

/** A filter by one property: a select offering every value the items have. */
export interface Facet<T> {
  label: string;
  value: (item: T) => string | string[] | null | undefined;
  /** Fixed options in this order; otherwise every value present, sorted. */
  options?: string[];
}

const PAGE_SIZES = [10, 20, 50, 100];

const values = (v: string | string[] | null | undefined) => (v == null ? [] : Array.isArray(v) ? v : [v]);

/** The list every page shares: a search box, a select per facet, how many match,
 * and pages. How an item looks stays the page's own (`children`).
 *
 * Filtering and paging happen here, on what the page loaded: every list in the
 * console is small enough to come in one request. */
export function ListView<T>({
  items,
  keyOf,
  text,
  facets = [],
  pageSize = 20,
  empty = "Nothing yet.",
  className,
  children,
}: {
  items: T[];
  keyOf: (item: T) => string;
  /** The text the search box looks in; no search box without it. */
  text?: (item: T) => string;
  facets?: Facet<T>[];
  pageSize?: number;
  /** Shown when there are no items at all, as opposed to none matching. */
  empty?: ReactNode;
  /** For the element holding the items, a grid with gaps by default. */
  className?: string;
  children: (item: T) => ReactNode;
}) {
  const [query, setQuery] = useState("");
  const [chosen, setChosen] = useState<Record<string, string>>({});
  const [page, setPage] = useState(0);
  const [size, setSize] = useState(pageSize);
  const options = useMemo(
    () => facets.map((f) => f.options ?? [...new Set(items.flatMap((i) => values(f.value(i))))].sort()),
    [facets, items],
  );
  const needle = query.trim().toLowerCase();
  const shown = items.filter(
    (item) =>
      (!needle || !text || text(item).toLowerCase().includes(needle)) &&
      facets.every((f) => !chosen[f.label] || values(f.value(item)).includes(chosen[f.label])),
  );
  const pages = Math.max(1, Math.ceil(shown.length / size));
  // A list that shrank (a filter, a delete) must not strand the view past its end.
  const current = Math.min(page, pages - 1);
  const filtering = Boolean(needle) || Object.values(chosen).some(Boolean);
  const choose = (label: string, value: string) => {
    setChosen({ ...chosen, [label]: value });
    setPage(0);
  };
  return (
    <div className="space-y-3">
      {text || facets.length ? (
        <div className="flex flex-wrap items-center gap-2">
          {text ? (
            <div className="relative min-w-40 flex-1">
              <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                className="pl-9"
                placeholder="Filter"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setPage(0);
                }}
              />
            </div>
          ) : null}
          {/* A facet with one value has nothing to choose between; it shows again once chosen. */}
          {facets.map((f, i) =>
            options[i].length > 1 || chosen[f.label] ? (
              <NativeSelect key={f.label} className="w-auto min-w-32" value={chosen[f.label] ?? ""} onChange={(e) => choose(f.label, e.target.value)} aria-label={f.label}>
                <option value="">All {f.label}</option>
                {options[i].map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </NativeSelect>
            ) : null,
          )}
          <span className="text-xs text-muted-foreground tabular-nums">{filtering ? `${shown.length} of ${items.length}` : items.length}</span>
        </div>
      ) : null}
      {items.length === 0 ? (
        <Empty>{empty}</Empty>
      ) : shown.length === 0 ? (
        <Empty>Nothing matches.</Empty>
      ) : (
        <div className={cn("grid gap-3", className)}>
          {shown.slice(current * size, (current + 1) * size).map((item) => (
            <Fragment key={keyOf(item)}>{children(item)}</Fragment>
          ))}
        </div>
      )}
      {/* Offered once a list is longer than the smallest page, so it can be made shorter as well as longer. */}
      {shown.length > PAGE_SIZES[0] ? (
        <div className="flex flex-wrap items-center justify-center gap-2">
          <NativeSelect
            className="w-auto"
            value={size}
            onChange={(e) => {
              // Keep the first item on screen in view rather than jumping back to the start.
              const first = current * size;
              const next = Number(e.target.value);
              setSize(next);
              setPage(Math.floor(first / next));
            }}
            aria-label="Items per page"
          >
            {[...new Set([...PAGE_SIZES, pageSize])]
              .sort((a, b) => a - b)
              .map((n) => (
                <option key={n} value={n}>
                  {n} per page
                </option>
              ))}
          </NativeSelect>
          <Button variant="outline" size="icon" disabled={current === 0} onClick={() => setPage(current - 1)} aria-label="Previous page">
            <ChevronLeft />
          </Button>
          <span className="text-sm text-muted-foreground tabular-nums">
            {current + 1} / {pages}
          </span>
          <Button variant="outline" size="icon" disabled={current >= pages - 1} onClick={() => setPage(current + 1)} aria-label="Next page">
            <ChevronRight />
          </Button>
        </div>
      ) : null}
    </div>
  );
}
