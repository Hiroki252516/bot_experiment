"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

import { apiFetch } from "../lib/api";

type AuthUserResponse = {
  user_id: string;
  username: string;
  display_name: string | null;
  active_skill_revision_id: string | null;
};

type AuthWorkspaceProps = {
  mode: "login" | "register";
};

export function AuthWorkspace({ mode }: AuthWorkspaceProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setStatus(mode === "register" ? "新規登録しています..." : "ログインしています...");
    try {
      await apiFetch<AuthUserResponse>(mode === "register" ? "/api/auth/register" : "/api/auth/login", {
        method: "POST",
        body: JSON.stringify(
          mode === "register"
            ? { username, password, display_name: displayName || null }
            : { username, password },
        ),
      });
      window.location.href = "/";
    } catch (requestError) {
      setStatus("");
      setError(requestError instanceof Error ? requestError.message : "認証に失敗しました。");
    }
  }

  return (
    <section className="card stack" style={{ maxWidth: 620, margin: "0 auto" }}>
      <div>
        <p className="muted">ユーザー管理</p>
        <h1>{mode === "register" ? "新規登録" : "ログイン"}</h1>
        <p className="muted">
          {mode === "register"
            ? "チャットで回答候補を選択し、次回以降の説明方針へ反映するためのユーザーを作成します。"
            : "登録済みユーザーでログインすると、チャットとスキル更新を同じユーザーに紐づけます。"}
        </p>
      </div>
      <form className="stack" onSubmit={handleSubmit}>
        <label className="field">
          <span>ユーザー名</span>
          <input
            autoComplete="username"
            onChange={(event) => setUsername(event.target.value)}
            placeholder="例: student01"
            required
            value={username}
          />
        </label>
        {mode === "register" ? (
          <label className="field">
            <span>表示名</span>
            <input
              autoComplete="name"
              onChange={(event) => setDisplayName(event.target.value)}
              placeholder="任意"
              value={displayName}
            />
          </label>
        ) : null}
        <label className="field">
          <span>パスワード</span>
          <input
            autoComplete={mode === "register" ? "new-password" : "current-password"}
            minLength={mode === "register" ? 8 : 1}
            onChange={(event) => setPassword(event.target.value)}
            required
            type="password"
            value={password}
          />
        </label>
        <button className="button" type="submit">
          {mode === "register" ? "新規登録してチャットへ進む" : "ログインしてチャットへ進む"}
        </button>
      </form>
      {status ? <p className="muted">{status}</p> : null}
      {error ? <p style={{ color: "#8d3f24" }}>{error}</p> : null}
      <p className="muted">
        {mode === "register" ? (
          <>
            すでに登録済みの場合は <Link href="/login">ログイン</Link> してください。
          </>
        ) : (
          <>
            初めて使う場合は <Link href="/register">新規登録</Link> してください。
          </>
        )}
      </p>
    </section>
  );
}
