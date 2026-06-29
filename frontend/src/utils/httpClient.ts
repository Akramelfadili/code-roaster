import { HTTP_STATUS } from '@/constants/api';
import { AppError, AppErrorCode } from '@/types/errors';
import { parseApiError } from '@/utils/errors';

function classifyHttpError(status: number, message: string): AppError {
  if (status === HTTP_STATUS.RateLimit) {
    return new AppError(AppErrorCode.RateLimitError, message, status);
  }
  if (status === HTTP_STATUS.UnprocessableEntity) {
    return new AppError(AppErrorCode.ValidationError, message, status);
  }
  return new AppError(AppErrorCode.ApiError, message, status);
}

async function postRequest(
  endpoint: string,
  body: unknown,
  signal?: AbortSignal
): Promise<Response> {
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const message =
      (data as { detail?: string }).detail ?? `Request failed (${response.status})`;
    throw classifyHttpError(response.status, message);
  }
  return response;
}

async function post<T>(endpoint: string, body: unknown): Promise<T> {
  try {
    const response = await postRequest(endpoint, body);
    return response.json() as Promise<T>;
  } catch (error) {
    throw parseApiError(error);
  }
}

async function stream(
  endpoint: string,
  body: unknown,
  onChunk: (chunk: string) => void,
  signal: AbortSignal
): Promise<void> {
  let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
  try {
    const response = await postRequest(endpoint, body, signal);
    if (!response.body)
      throw new AppError(AppErrorCode.ApiError, 'Response has no body');

    reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        const remaining = decoder.decode();
        if (remaining) onChunk(remaining);
        break;
      }
      onChunk(decoder.decode(value, { stream: true }));
    }
  } catch (error) {
    throw parseApiError(error);
  } finally {
    reader?.releaseLock();
  }
}

export const httpClient = { post, stream };
