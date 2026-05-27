"use client";

import { usePathname, useSearchParams, type ReadonlyURLSearchParams } from "next/navigation";
import { useRef } from "react";

export type UrlSnapshot = Readonly<{
  pathname: string;
  search: string;
}>;

const EMPTY_URL_SNAPSHOT: UrlSnapshot = {
  pathname: "",
  search: "",
};

export function resolveUrlSnapshot(
  previousSnapshot: UrlSnapshot,
  pathname: string,
  search: string,
): UrlSnapshot {
  if (previousSnapshot.pathname === pathname && previousSnapshot.search === search) {
    return previousSnapshot;
  }

  return {
    pathname,
    search,
  };
}

export function resolveSearchFromParams(
  searchParams: URLSearchParams | ReadonlyURLSearchParams | null | undefined,
): string {
  const nextSearch = searchParams?.toString() ?? "";
  return nextSearch.length > 0 ? `?${nextSearch}` : "";
}

export function useUrlState(): UrlSnapshot {
  const pathname = usePathname() ?? "";
  const searchParams = useSearchParams();
  const previousSnapshotRef = useRef<UrlSnapshot>(EMPTY_URL_SNAPSHOT);

  const snapshot = resolveUrlSnapshot(
    previousSnapshotRef.current,
    pathname,
    resolveSearchFromParams(searchParams),
  );
  previousSnapshotRef.current = snapshot;

  return snapshot;
}
