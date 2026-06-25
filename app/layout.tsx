import "./globals.css";

export const metadata = {
  title: "🌙 ネドココ",
  description:
    "AIがぶい睡（VR睡眠）に向いたVRChatワールドを厳選。新着・人気・お気に入りで探したり、ランダムで出会ったり。",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}
