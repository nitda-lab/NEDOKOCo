export default async function AdminLogin({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  const { error } = await searchParams;
  return (
    <main style={{ maxWidth: 400, margin: "80px auto", padding: 24 }}>
      <h1 style={{ color: "var(--accent)" }}>管理ログイン</h1>
      {error && <p style={{ color: "#ff6b6b" }}>パスワードが違います</p>}
      <form action="/api/admin/login" method="post" style={{ display: "flex", gap: 8 }}>
        <input type="password" name="password" placeholder="パスワード" style={{ flex: 1, padding: 8 }} />
        <button type="submit" style={{ background: "var(--accent)", color: "#fff", border: "none", borderRadius: 8, padding: "8px 16px" }}>
          ログイン
        </button>
      </form>
    </main>
  );
}
