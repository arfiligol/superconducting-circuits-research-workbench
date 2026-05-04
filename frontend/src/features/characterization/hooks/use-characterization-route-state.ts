"use client";

import { useCallback, useMemo, useTransition } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import {
  buildCharacterizationSearchHref,
  shouldSyncCharacterizationUrl,
  type CharacterizationResultSelectionSource,
} from "@/features/characterization/lib/workflow";

function parseTaskIdParam(value: string | null): number | null {
  if (!value) {
    return null;
  }

  const parsedValue = Number.parseInt(value, 10);
  return Number.isFinite(parsedValue) ? parsedValue : null;
}

export type CharacterizationRouteIntent = Readonly<{
  requestedDesignId: string | null;
  requestedResultId: string | null;
  selectedTaskId: number | null;
}>;

export function useCharacterizationRouteState() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const searchParamsValue = searchParams.toString();
  const [, startTransition] = useTransition();

  const routeIntent = useMemo<CharacterizationRouteIntent>(
    () => ({
      requestedDesignId: searchParams.get("designId"),
      requestedResultId: searchParams.get("resultId"),
      selectedTaskId: parseTaskIdParam(searchParams.get("taskId")),
    }),
    [searchParams],
  );

  const syncRouteState = useCallback(
    (input: Readonly<{
      designId: string | null;
      resultId: string | null;
      taskId: number | null;
      isExplicitRouteResultPending: boolean;
      resolvedResultSource: CharacterizationResultSelectionSource;
    }>) => {
      const nextHref = buildCharacterizationSearchHref(pathname, searchParamsValue, {
        designId: input.designId,
        resultId: input.resultId,
        taskId: input.taskId ? String(input.taskId) : null,
      });
      const currentHref = searchParamsValue ? `${pathname}?${searchParamsValue}` : pathname;

      if (
        !shouldSyncCharacterizationUrl({
          currentHref,
          nextHref,
          hasExplicitRouteResult: Boolean(routeIntent.requestedResultId),
          isExplicitRouteResultPending: input.isExplicitRouteResultPending,
          resolvedResultSource: input.resolvedResultSource,
        })
      ) {
        return;
      }

      startTransition(() => {
        router.replace(nextHref, { scroll: false });
      });
    },
    [pathname, routeIntent.requestedResultId, router, searchParamsValue, startTransition],
  );

  return {
    routeIntent,
    searchParamsValue,
    syncRouteState,
  };
}
