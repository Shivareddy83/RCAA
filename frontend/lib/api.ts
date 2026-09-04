export type ApiErrorShape = {
  status: number;
  message: string;
  requestId?: string;
};

export class ApiError extends Error implements ApiErrorShape {
  status: number;
  requestId?: string;

  constructor(
    status: number,
    message: string,
    requestId?: string,
  ) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.requestId = requestId;
  }
}

/*
 * Authentication token is intentionally kept in memory only.
 *
 * Security model:
 * - No localStorage.
 * - No sessionStorage.
 * - No persistent browser token.
 * - Token disappears when the page is fully reloaded.
 *
 * This matches the current RCAA authentication design.
 */
let accessToken: string | null = null;

export function setToken(token: string): void {
  accessToken = token;
}

export function getToken(): string | null {
  return accessToken;
}

export function clearToken(): void {
  accessToken = null;
}

function safeErrorMessage(
  status: number,
  authenticatedSession: boolean,
): string {
  if (status === 400) {
    return 'The request could not be processed.';
  }

  if (status === 401) {
    return authenticatedSession
      ? 'Session expired or unauthorized.'
      : 'Invalid email or password.';
  }

  if (status === 403) {
    return 'You do not have permission for this action.';
  }

  if (status === 404) {
    return 'Resource not found.';
  }

  if (status === 409) {
    return 'The requested resource already exists.';
  }

  if (status === 422) {
    return 'The request could not be validated.';
  }

  if (status === 429) {
    return 'Too many requests. Please try again shortly.';
  }

  if (status >= 500) {
    return 'The backend is temporarily unavailable. Please try again.';
  }

  return 'The request could not be completed.';
}

export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const baseUrl =
    process.env.NEXT_PUBLIC_API_URL ||
    'http://localhost:8000/api/v1';

  /*
   * Capture the token BEFORE making the request.
   *
   * This is important because a 401 has two different meanings:
   *
   * 1. No token exists:
   *    login failed
   *    -> "Invalid email or password."
   *
   * 2. Token exists:
   *    existing session became unauthorized/expired
   *    -> clear token
   *    -> emit auth-expired
   *    -> "Session expired or unauthorized."
   */
  const token = getToken();
  const hadAuthenticatedSession = Boolean(token);

  const headers = new Headers(options.headers);

  if (
    options.body &&
    !headers.has('Content-Type')
  ) {
    headers.set(
      'Content-Type',
      'application/json',
    );
  }

  if (token) {
    headers.set(
      'Authorization',
      `Bearer ${token}`,
    );
  }

  const requestId =
    typeof crypto !== 'undefined' &&
    typeof crypto.randomUUID === 'function'
      ? crypto.randomUUID()
      : undefined;

  if (requestId) {
    headers.set(
      'X-Request-ID',
      requestId,
    );
  }

  let response: Response;

  try {
    response = await fetch(
      `${baseUrl}${path}`,
      {
        ...options,
        headers,
      },
    );
  } catch {
    throw new ApiError(
      0,
      'Unable to connect to the backend. Please try again.',
      requestId,
    );
  }

  const responseRequestId =
    response.headers.get('x-request-id') ||
    requestId ||
    undefined;

  if (!response.ok) {
    /*
     * Only an already-authenticated session should
     * trigger the global auth-expired behavior.
     *
     * A login 401 must remain on the login page so
     * the user can see "Invalid email or password."
     */
    if (
      response.status === 401 &&
      hadAuthenticatedSession
    ) {
      clearToken();

      if (typeof window !== 'undefined') {
        window.dispatchEvent(
          new Event('rcaa:auth-expired'),
        );
      }
    }

    throw new ApiError(
      response.status,
      safeErrorMessage(
        response.status,
        hadAuthenticatedSession,
      ),
      responseRequestId,
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType =
    response.headers.get('content-type') || '';

  if (
    contentType.includes('application/json')
  ) {
    return (await response.json()) as T;
  }

  return (await response.text()) as T;
}