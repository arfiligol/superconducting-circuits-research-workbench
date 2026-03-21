"use client";

type ApiErrorEnvelope = Readonly<{
  code?: string;
  error_code?: string;
  category?: string;
  message?: string;
  retryable?: boolean;
  details?: unknown;
  debug_ref?: string;
}>;

type ApiSuccessEnvelope<T> = Readonly<{
  ok: true;
  data: T;
  meta?: unknown;
}>;

export class ApiError extends Error {
  readonly status: number;
  readonly errorCode: string | null;
  readonly category: string | null;
  readonly retryable: boolean | null;
  readonly details: unknown;
  readonly debugRef: string | null;

  constructor(
    message: string,
    status: number,
    options?: Readonly<{
      errorCode?: string | null;
      category?: string | null;
      retryable?: boolean | null;
      details?: unknown;
      debugRef?: string | null;
    }>,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.errorCode = options?.errorCode ?? null;
    this.category = options?.category ?? null;
    this.retryable = options?.retryable ?? null;
    this.details = options?.details;
    this.debugRef = options?.debugRef ?? null;
  }
}

export type TaskEnqueueFailureDetails = Readonly<{
  taskId: number | null;
  dispatch: Readonly<{
    dispatchKey: string | null;
    queueName: string | null;
    runtimeJobId: string | null;
    dispatchAttemptCount: number | null;
    lastDispatchOutcome: string | null;
    lastDispatchErrorCode: string | null;
  }> | null;
}>;

type ApiRequestInit = Omit<RequestInit, "body"> & {
  body?: BodyInit | Record<string, unknown> | null;
};

export async function apiRequest<T>(path: string, init?: ApiRequestInit): Promise<T> {
  const payload = await apiRequestRaw(path, init);
  if (isSuccessEnvelope<T>(payload)) {
    return payload.data;
  }
  return payload as T;
}

export async function apiRequestEnvelope<TData, TMeta = unknown>(
  path: string,
  init?: ApiRequestInit,
): Promise<
  Readonly<{
    data: TData;
    meta: TMeta | undefined;
  }>
> {
  const payload = await apiRequestRaw(path, init);
  if (isSuccessEnvelope<TData>(payload)) {
    return {
      data: payload.data,
      meta: payload.meta as TMeta | undefined,
    };
  }
  return {
    data: payload as TData,
    meta: undefined,
  };
}

export function getTaskEnqueueFailureDetails(error: unknown): TaskEnqueueFailureDetails | null {
  if (!(error instanceof ApiError) || error.errorCode !== "task_enqueue_failed") {
    return null;
  }

  const details =
    typeof error.details === "object" && error.details !== null
      ? (error.details as Record<string, unknown>)
      : null;
  const dispatch =
    details && typeof details.dispatch === "object" && details.dispatch !== null
      ? (details.dispatch as Record<string, unknown>)
      : null;

  return {
    taskId: typeof details?.task_id === "number" ? details.task_id : null,
    dispatch: dispatch
      ? {
          dispatchKey:
            typeof dispatch.dispatch_key === "string" ? dispatch.dispatch_key : null,
          queueName: typeof dispatch.queue_name === "string" ? dispatch.queue_name : null,
          runtimeJobId:
            typeof dispatch.runtime_job_id === "string" ? dispatch.runtime_job_id : null,
          dispatchAttemptCount:
            typeof dispatch.dispatch_attempt_count === "number"
              ? dispatch.dispatch_attempt_count
              : null,
          lastDispatchOutcome:
            typeof dispatch.last_dispatch_outcome === "string"
              ? dispatch.last_dispatch_outcome
              : null,
          lastDispatchErrorCode:
            typeof dispatch.last_dispatch_error_code === "string"
              ? dispatch.last_dispatch_error_code
              : null,
        }
      : null,
  };
}

async function apiRequestRaw(path: string, init?: ApiRequestInit): Promise<unknown> {
  const { body, headers, ...requestInit } = init ?? {};
  const isJsonBody = body !== undefined && body !== null && !(body instanceof FormData);

  const response = await fetch(path, {
    ...requestInit,
    headers: {
      ...(isJsonBody ? { "Content-Type": "application/json" } : {}),
      ...headers,
    },
    body: isJsonBody ? JSON.stringify(body) : (body ?? undefined),
  });

  if (!response.ok) {
    const errorPayload = await getApiErrorPayload(response);
    throw new ApiError(errorPayload.message, response.status, {
      errorCode: errorPayload.errorCode,
      category: errorPayload.category,
      retryable: errorPayload.retryable,
      details: errorPayload.details,
      debugRef: errorPayload.debugRef,
    });
  }

  if (response.status === 204) {
    return undefined;
  }

  return await response.json();
}

async function getApiErrorPayload(response: Response): Promise<
  Readonly<{
    message: string;
    errorCode: string | null;
    category: string | null;
    retryable: boolean | null;
    details: unknown;
    debugRef: string | null;
  }>
> {
  try {
    const data = (await response.json()) as
      | ({
          detail?: string | ApiErrorEnvelope;
          error?: ApiErrorEnvelope;
          message?: string;
        } & ApiErrorEnvelope)
      | null;
    const errorEnvelope = data?.error && typeof data.error === "object" ? data.error : undefined;
    const detailEnvelope =
      data?.detail && typeof data.detail === "object" ? data.detail : undefined;
    const message =
      typeof data?.detail === "string"
        ? data.detail
        : (errorEnvelope?.message ??
            detailEnvelope?.message ??
            data?.message ??
            response.statusText ??
            "Unexpected API error");

    return {
      message,
      errorCode:
        errorEnvelope?.code ??
        errorEnvelope?.error_code ??
        detailEnvelope?.error_code ??
        data?.error_code ??
        null,
      category: errorEnvelope?.category ?? detailEnvelope?.category ?? data?.category ?? null,
      retryable: errorEnvelope?.retryable ?? detailEnvelope?.retryable ?? data?.retryable ?? null,
      details: errorEnvelope?.details ?? detailEnvelope?.details ?? data?.details,
      debugRef:
        errorEnvelope?.debug_ref ?? detailEnvelope?.debug_ref ?? data?.debug_ref ?? null,
    };
  } catch {
    return {
      message: response.statusText || "Unexpected API error",
      errorCode: null,
      category: null,
      retryable: null,
      details: undefined,
      debugRef: null,
    };
  }
}

function isSuccessEnvelope<T>(payload: unknown): payload is ApiSuccessEnvelope<T> {
  return (
    typeof payload === "object" &&
    payload !== null &&
    "ok" in payload &&
    (payload as { ok?: unknown }).ok === true &&
    "data" in payload
  );
}
