import "./globals.css";
import type { ReactNode } from "react";

import { AuthNav } from "../components/auth-nav";

export const metadata = {
  title: "スキル蓄積型学習支援チャットボット",
  description: "回答選択から学習者ごとの説明方針を更新する研究用プロトタイプ。",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ja">
      <body>
        <div className="page-shell">
          <AuthNav />
          {children}
        </div>
      </body>
    </html>
  );
}
