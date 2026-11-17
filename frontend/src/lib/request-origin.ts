import type { NextRequest } from "next/server";

/**
 * The origin the browser actually used (e.g. http://localhost:3000).
 *
 * `request.nextUrl.origin` reflects the server's bind address, which is
 * http://0.0.0.0:3000 under `next dev --hostname 0.0.0.0` (Docker). Redirecting there
 * moves the user to a different site, where their session cookie doesn't exist.
 * Prefer the proxy's forwarded host, then the Host header.
 */
export function requestOrigin(request: NextRequest): string {
  const host =
    request.headers.get("x-forwarded-host")?.split(",")[0]?.trim() ||
    request.headers.get("host");
  if (!host) return request.nextUrl.origin;
  const proto =
    request.headers.get("x-forwarded-proto")?.split(",")[0]?.trim() ||
    request.nextUrl.protocol.replace(/:$/, "");
  return `${proto}://${host}`;
}
