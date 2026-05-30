import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DoodleStory",
  description: "文本转图片故事生成工作台",
  icons: {
    icon: "/icon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
