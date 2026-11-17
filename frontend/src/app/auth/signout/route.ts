import { NextResponse, type NextRequest } from "next/server";
import { isAuthConfigured } from "@/lib/env";
import { requestOrigin } from "@/lib/request-origin";
import { createClient } from "@/lib/supabase/server";

// POST only, so a link or prefetch can't sign someone out.
export async function POST(request: NextRequest) {
  if (isAuthConfigured()) {
    const supabase = await createClient();
    await supabase.auth.signOut();
  }
  return NextResponse.redirect(new URL("/", requestOrigin(request)), { status: 303 });
}
