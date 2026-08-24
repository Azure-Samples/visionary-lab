import { randomUUID } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const ANONYMOUS_OWNER_COOKIE = "visionary-lab-anonymous-owner";
const ONE_YEAR_SECONDS = 60 * 60 * 24 * 365;
const HOP_BY_HOP_HEADERS = [
  "connection",
  "content-length",
  "host",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
];

function isAnonymousOwnerId(value: string | null | undefined): value is string {
  return Boolean(
    value &&
      /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
        value,
      ),
  );
}

function getConfiguredBackendRoot(): string {
  const protocol = process.env.NEXT_PUBLIC_API_PROTOCOL || "http";
  const hostname = process.env.NEXT_PUBLIC_API_HOSTNAME || "localhost";
  const port = process.env.NEXT_PUBLIC_API_PORT || "8000";
  const configured =
    process.env.BACKEND_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    (port ? `${protocol}://${hostname}:${port}` : `${protocol}://${hostname}`);
  return configured.replace(/\/api\/v1\/?$/, "").replace(/\/$/, "");
}

function getEasyAuthPrincipalId(request: NextRequest): string | null {
  const trustedId = request.headers
    .get("x-visionary-trusted-principal-id")
    ?.trim();
  return trustedId && trustedId.length <= 256 ? trustedId : null;
}

function createUpstreamHeaders(
  request: NextRequest,
  principalId: string | null,
  anonymousOwnerId: string,
): Headers {
  const headers = new Headers(request.headers);
  for (const header of Array.from(headers.keys())) {
    const normalized = header.toLowerCase();
    if (
      normalized === "authorization" ||
      normalized === "cookie" ||
      normalized === "x-image-job-owner" ||
      normalized.startsWith("x-visionary-") ||
      normalized.startsWith("x-ms-client-") ||
      normalized === "forwarded" ||
      normalized.startsWith("x-forwarded-") ||
      HOP_BY_HOP_HEADERS.includes(normalized)
    ) {
      headers.delete(header);
    }
  }
  headers.set("accept-encoding", "identity");
  if (principalId) {
    headers.set("x-ms-client-principal-id", principalId);
  } else {
    headers.set("x-image-job-owner", anonymousOwnerId);
  }
  return headers;
}

function createTargetUrl(request: NextRequest, path: string[]): string {
  const safePath = path.map((segment) => encodeURIComponent(segment)).join("/");
  return `${getConfiguredBackendRoot()}/${safePath}${request.nextUrl.search}`;
}

async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
): Promise<NextResponse> {
  const { path } = await context.params;
  if (!Array.isArray(path) || path.length === 0) {
    return NextResponse.json({ detail: "A backend path is required" }, { status: 400 });
  }

  const principalId = getEasyAuthPrincipalId(request);
  const existingAnonymousOwner = request.cookies.get(ANONYMOUS_OWNER_COOKIE)?.value;
  const middlewareAnonymousOwner = request.headers.get(
    "x-visionary-trusted-anonymous-owner",
  );
  const hasMiddlewareAnonymousOwner = isAnonymousOwnerId(
    middlewareAnonymousOwner,
  );
  const anonymousOwnerId = isAnonymousOwnerId(middlewareAnonymousOwner)
    ? middlewareAnonymousOwner
    : isAnonymousOwnerId(existingAnonymousOwner)
      ? existingAnonymousOwner
      : randomUUID();
  const upstreamHeaders = createUpstreamHeaders(
    request,
    principalId,
    anonymousOwnerId,
  );
  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  const init: RequestInit & { duplex?: "half" } = {
    method: request.method,
    headers: upstreamHeaders,
    body: hasBody ? request.body : undefined,
    cache: "no-store",
    redirect: "manual",
    signal: request.signal,
  };
  if (hasBody && request.body) init.duplex = "half";

  try {
    const upstream = await fetch(createTargetUrl(request, path), init);
    const responseHeaders = new Headers(upstream.headers);
    for (const header of [
      ...HOP_BY_HOP_HEADERS,
      "access-control-allow-credentials",
      "access-control-allow-headers",
      "access-control-allow-methods",
      "access-control-allow-origin",
      "content-encoding",
      "content-length",
    ]) {
      responseHeaders.delete(header);
    }
    const location = responseHeaders.get("location");
    if (location) {
      try {
        const locationUrl = new URL(location);
        const backendUrl = new URL(getConfiguredBackendRoot());
        if (locationUrl.origin === backendUrl.origin) {
          responseHeaders.set(
            "location",
            `/api/backend${locationUrl.pathname}${locationUrl.search}`,
          );
        }
      } catch {
        // Relative upstream locations already remain on the proxy origin.
      }
    }
    responseHeaders.set("cache-control", "private, no-store, max-age=0");
    responseHeaders.set("pragma", "no-cache");

    const response = new NextResponse(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: responseHeaders,
    });
    if (
      !principalId &&
      !isAnonymousOwnerId(existingAnonymousOwner) &&
      !hasMiddlewareAnonymousOwner
    ) {
      response.cookies.set(ANONYMOUS_OWNER_COOKIE, anonymousOwnerId, {
        httpOnly: true,
        sameSite: "lax",
        secure: request.nextUrl.protocol === "https:",
        path: "/",
        maxAge: ONE_YEAR_SECONDS,
      });
    }
    return response;
  } catch (error) {
    console.error("Backend proxy request failed", error);
    const response = NextResponse.json(
      { detail: "The backend service is temporarily unavailable" },
      {
        status: 502,
        headers: {
          "Cache-Control": "private, no-store, max-age=0",
        },
      },
    );
    if (
      !principalId &&
      !isAnonymousOwnerId(existingAnonymousOwner) &&
      !hasMiddlewareAnonymousOwner
    ) {
      response.cookies.set(ANONYMOUS_OWNER_COOKIE, anonymousOwnerId, {
        httpOnly: true,
        sameSite: "lax",
        secure: request.nextUrl.protocol === "https:",
        path: "/",
        maxAge: ONE_YEAR_SECONDS,
      });
    }
    return response;
  }
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const OPTIONS = proxy;
export const HEAD = proxy;
