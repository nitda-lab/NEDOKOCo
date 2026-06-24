import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  const form = await req.formData();
  const password = String(form.get("password") || "");
  if (!process.env.ADMIN_PASSWORD || password !== process.env.ADMIN_PASSWORD) {
    return NextResponse.redirect(new URL("/admin/login?error=1", req.url), 303);
  }
  const res = NextResponse.redirect(new URL("/admin", req.url), 303);
  res.cookies.set("admin_token", process.env.ADMIN_TOKEN || "", {
    httpOnly: true, secure: true, sameSite: "lax", path: "/", maxAge: 60 * 60 * 24 * 7,
  });
  return res;
}
