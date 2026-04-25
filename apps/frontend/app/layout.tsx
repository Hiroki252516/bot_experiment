import "./globals.css";
import Link from "next/link";
import type { ReactNode } from "react";

export const metadata = {
  title: "スキル蓄積型学習支援チャットボット",
  description: "回答選択から学習者ごとの説明方針を更新する研究用プロトタイプ。",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ja">
      <body>
        <div className="page-shell">
          <nav className="top-nav">
            <Link href="/">チャット</Link>
            <Link href="/logs">会話ログ</Link>
            <Link href="/admin">管理</Link>
          </nav>
          {children}
        </div>
      </body>
    </html>
  );
}
