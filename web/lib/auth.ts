export function adminToken(): string {
  return process.env.ADMIN_TOKEN || "";
}

export function adminPassword(): string {
  return process.env.ADMIN_PASSWORD || "";
}

export function isAuthed(token: string | undefined): boolean {
  const expected = adminToken();
  return !!expected && token === expected;
}
