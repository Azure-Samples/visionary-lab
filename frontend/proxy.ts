import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const ANONYMOUS_OWNER_COOKIE = 'visionary-lab-anonymous-owner';
const ONE_YEAR_SECONDS = 60 * 60 * 24 * 365;

function getAnonymousOwner(request: NextRequest): string | null {
  const value = request.cookies.get(ANONYMOUS_OWNER_COOKIE)?.value;
  return (
    value &&
      /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
        value,
      )
  ) ? value : null;
}

function withAnonymousOwner(
  request: NextRequest,
  response: NextResponse,
): NextResponse {
  const principalId = request.headers.get('x-ms-client-principal-id')?.trim();
  if (!principalId && !getAnonymousOwner(request)) {
    response.cookies.set(ANONYMOUS_OWNER_COOKIE, crypto.randomUUID(), {
      httpOnly: true,
      sameSite: 'lax',
      secure: request.nextUrl.protocol === 'https:',
      path: '/',
      maxAge: ONE_YEAR_SECONDS,
    });
  }
  return response;
}

export function proxy(request: NextRequest) {
  const path = request.nextUrl.pathname;

  if (path.startsWith('/api/backend/')) {
    const requestHeaders = new Headers(request.headers);
    requestHeaders.delete('x-visionary-trusted-principal-id');
    requestHeaders.delete('x-visionary-trusted-anonymous-owner');
    const principalId = request.headers.get('x-ms-client-principal-id')?.trim();
    let generatedAnonymousOwner: string | null = null;
    if (principalId && principalId.length <= 256) {
      requestHeaders.set('x-visionary-trusted-principal-id', principalId);
    } else if (!getAnonymousOwner(request)) {
      generatedAnonymousOwner = crypto.randomUUID();
      requestHeaders.set('x-visionary-trusted-anonymous-owner', generatedAnonymousOwner);
    }
    const response = NextResponse.next({ request: { headers: requestHeaders } });
    if (generatedAnonymousOwner) {
      response.cookies.set(ANONYMOUS_OWNER_COOKIE, generatedAnonymousOwner, {
        httpOnly: true,
        sameSite: 'lax',
        secure: request.nextUrl.protocol === 'https:',
        path: '/',
        maxAge: ONE_YEAR_SECONDS,
      });
    }
    return response;
  }

  return withAnonymousOwner(request, NextResponse.next());
}

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|sw.js|manifest.json|logo/).*)',
  ],
};
