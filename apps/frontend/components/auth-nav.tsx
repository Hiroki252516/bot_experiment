"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { apiFetch } from "../lib/api";

type AuthUserResponse = {
  user_id: string;
  username: string;
  display_name: string | null;
};

export function AuthNav() {
  const [user, setUser] = useState<AuthUserResponse | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    async function loadCurrentUser() {
      try {
        const currentUser = await apiFetch<AuthUserResponse>("/api/auth/me");
        setUser(currentUser);
      } catch {
        setUser(null);
      } finally {
        setLoaded(true);
      }
    }
    loadCurrentUser();
  }, []);

  async function handleLogout() {
    await apiFetch("/api/auth/logout", { method: "POST" });
    setUser(null);
    window.location.href = "/login";
  }

  return (
    <nav className="top-nav">
      <Link href="/">チャット</Link>
      <Link href="/logs">会話ログ</Link>
      <Link href="/admin">管理</Link>
      {loaded && user ? (
        <>
          <span className="nav-user">ログイン中: {user.display_name || user.username}</span>
          <button className="nav-button" onClick={handleLogout} type="button">
            ログアウト
          </button>
        </>
      ) : null}
      {loaded && !user ? (
        <>
          <Link href="/login">ログイン</Link>
          <Link href="/register">新規登録</Link>
        </>
      ) : null}
    </nav>
  );
}
