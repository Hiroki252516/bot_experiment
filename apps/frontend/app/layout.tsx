import "./globals.css";
import Link from "next/link";
import type { ReactNode } from "react";

export const metadata = {
  title: "Learning Skill Accumulation Chatbot",
  description: "Research prototype for adaptive tutoring with skill accumulation.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="page-shell">
          <nav className="top-nav">
            <Link href="/">Chat</Link>
            <Link href="/logs">Chat Logs</Link>
            <Link href="/admin">Admin</Link>
          </nav>
          {children}
        </div>
      </body>
    </html>
  );
}

