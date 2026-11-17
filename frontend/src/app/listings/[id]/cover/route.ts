import { NextResponse, type NextRequest } from "next/server";
import { getListing } from "@/lib/api";
import { requestOrigin } from "@/lib/request-origin";

/**
 * Stable cover-photo URL for link previews (WhatsApp, Facebook). Photos live in a private
 * bucket behind short-lived signed URLs, so a preview can't point at one directly. This
 * fetches the listing anonymously (only live listings are public), then redirects to a
 * fresh signed URL, shrunk by Next's image optimizer so preview fetchers accept it.
 */
export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const listing = await getListing(id).catch(() => null);
  const cover = listing?.status === "active" ? listing.images[0] : undefined;
  if (!cover) return new NextResponse(null, { status: 404 });

  const optimized = new URL("/_next/image", requestOrigin(request));
  optimized.searchParams.set("url", cover.url);
  optimized.searchParams.set("w", "1200");
  optimized.searchParams.set("q", "75");
  return NextResponse.redirect(optimized, {
    status: 302,
    headers: { "Cache-Control": "public, max-age=300" },
  });
}
