type SearchParamsLike = Readonly<{
  get(name: string): string | null;
}>;

export type RawDataBrowseState = Readonly<{
  designId: string | null;
  traceId: string | null;
  designQuery: string | null;
}>;

export function parseRawDataBrowseState(searchParams: SearchParamsLike): RawDataBrowseState {
  return {
    designId: searchParams.get("designId"),
    traceId: searchParams.get("traceId"),
    designQuery: searchParams.get("designQuery"),
  };
}

export function buildRawDataBrowseHref(input?: Partial<RawDataBrowseState>) {
  const params = new URLSearchParams();
  if (input?.designId) {
    params.set("designId", input.designId);
  }
  if (input?.traceId) {
    params.set("traceId", input.traceId);
  }
  if (input?.designQuery) {
    params.set("designQuery", input.designQuery);
  }

  const query = params.toString();
  return query ? `/raw-data?${query}` : "/raw-data";
}
