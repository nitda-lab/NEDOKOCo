import "./globals.css";

export const metadata = { title: "ぶい睡ワールド", description: "VRChat ぶい睡ワールド推薦" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}
