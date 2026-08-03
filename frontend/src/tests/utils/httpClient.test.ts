import { describe, it, expect, vi, afterEach } from 'vitest';

import { AppErrorCode } from '@/types/errors';
import { httpClient } from '@/utils/httpClient';

const ENDPOINT = '/api/test';

interface MockResponseOptions {
  ok?: boolean;
  status?: number;
  jsonBody?: unknown;
  body?: unknown;
}

function mockResponse(options: MockResponseOptions = {}): Response {
  const { ok = true, status = 200, jsonBody = {}, body } = options;
  return {
    ok,
    status,
    json: () => Promise.resolve(jsonBody),
    body,
  } as unknown as Response;
}

describe('httpClient', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe('get', () => {
    it('returns parsed JSON on success', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue(mockResponse({ jsonBody: { foo: 'bar' } }))
      );

      const result = await httpClient.get(ENDPOINT);

      expect(result).toEqual({ foo: 'bar' });
    });

    it('classifies a 429 response as RateLimitError', async () => {
      vi.stubGlobal(
        'fetch',
        vi
          .fn()
          .mockResolvedValue(
            mockResponse({ ok: false, status: 429, jsonBody: { detail: 'slow down' } })
          )
      );

      await expect(httpClient.get(ENDPOINT)).rejects.toMatchObject({
        code: AppErrorCode.RateLimitError,
        message: 'slow down',
        statusCode: 429,
      });
    });

    it('classifies a 422 response as ValidationError', async () => {
      vi.stubGlobal(
        'fetch',
        vi
          .fn()
          .mockResolvedValue(
            mockResponse({ ok: false, status: 422, jsonBody: { detail: 'bad input' } })
          )
      );

      await expect(httpClient.get(ENDPOINT)).rejects.toMatchObject({
        code: AppErrorCode.ValidationError,
      });
    });

    it('classifies any other non-ok status as ApiError, defaulting the message when body has no detail', async () => {
      vi.stubGlobal(
        'fetch',
        vi
          .fn()
          .mockResolvedValue(mockResponse({ ok: false, status: 500, jsonBody: {} }))
      );

      await expect(httpClient.get(ENDPOINT)).rejects.toMatchObject({
        code: AppErrorCode.ApiError,
        message: 'Request failed (500)',
      });
    });

    it('wraps a network failure as a NetworkError', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
      );

      await expect(httpClient.get(ENDPOINT)).rejects.toMatchObject({
        code: AppErrorCode.NetworkError,
      });
    });
  });

  describe('post', () => {
    it('sends a JSON POST request and returns parsed JSON on success', async () => {
      const mockFetch = vi
        .fn()
        .mockResolvedValue(mockResponse({ jsonBody: { ok: true } }));
      vi.stubGlobal('fetch', mockFetch);

      const result = await httpClient.post(ENDPOINT, { code: 'x' });

      expect(mockFetch).toHaveBeenCalledWith(ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: 'x' }),
        signal: undefined,
      });
      expect(result).toEqual({ ok: true });
    });

    it('wraps a non-ok response in an AppError', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue(
          mockResponse({
            ok: false,
            status: 400,
            jsonBody: { detail: 'bad request' },
          })
        )
      );

      await expect(httpClient.post(ENDPOINT, {})).rejects.toMatchObject({
        code: AppErrorCode.ApiError,
        message: 'bad request',
      });
    });
  });

  describe('stream', () => {
    function mockStreamResponse(chunks: string[]): Response {
      const encoder = new TextEncoder();
      const values = chunks.map((chunk) => encoder.encode(chunk));
      let index = 0;
      const reader = {
        read: vi.fn(async () => {
          if (index < values.length) {
            const value = values[index];
            index += 1;
            return { done: false, value };
          }
          return { done: true, value: undefined };
        }),
        releaseLock: vi.fn(),
      };
      return mockResponse({ body: { getReader: () => reader } });
    }

    it('decodes and emits each chunk via onChunk', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue(mockStreamResponse(['hello ', 'world']))
      );

      const chunks: string[] = [];
      await httpClient.stream(
        ENDPOINT,
        {},
        (chunk) => chunks.push(chunk),
        new AbortController().signal
      );

      expect(chunks).toEqual(['hello ', 'world']);
    });

    it('throws an AppError when the response has no body', async () => {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockResponse({ body: null })));

      await expect(
        httpClient.stream(ENDPOINT, {}, () => {}, new AbortController().signal)
      ).rejects.toMatchObject({
        code: AppErrorCode.ApiError,
        message: 'Response has no body',
      });
    });

    it('releases the reader lock even when an error occurs mid-stream', async () => {
      const releaseLock = vi.fn();
      const reader = {
        read: vi.fn().mockRejectedValue(new TypeError('stream broke')),
        releaseLock,
      };
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue(mockResponse({ body: { getReader: () => reader } }))
      );

      await expect(
        httpClient.stream(ENDPOINT, {}, () => {}, new AbortController().signal)
      ).rejects.toMatchObject({ code: AppErrorCode.NetworkError });
      expect(releaseLock).toHaveBeenCalled();
    });

    it('reports cancellation as a NetworkError AppError when the request is aborted', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockRejectedValue(new DOMException('Aborted', 'AbortError'))
      );

      await expect(
        httpClient.stream(ENDPOINT, {}, () => {}, new AbortController().signal)
      ).rejects.toMatchObject({
        code: AppErrorCode.NetworkError,
        message: 'Request was cancelled',
      });
    });
  });
});
