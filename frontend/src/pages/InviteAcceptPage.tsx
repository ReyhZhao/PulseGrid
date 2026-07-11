import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { api, errorMessage } from "../lib/api";
import type { Organization } from "../lib/types";

export default function InviteAcceptPage() {
  const { token } = useParams<{ token: string }>();
  const { refresh } = useAuth();
  const [state, setState] = useState<"working" | "joined" | "error">("working");
  const [orgName, setOrgName] = useState("");
  const [error, setError] = useState("");
  const accepted = useRef(false);

  useEffect(() => {
    if (accepted.current || !token) return;
    accepted.current = true; // StrictMode double-invoke guard: token is single-use
    api<{ organization: Organization; joined: boolean }>("/api/v1/invitations/accept", {
      method: "POST",
      body: { token },
    })
      .then(async (result) => {
        setOrgName(result.organization.name);
        await refresh();
        setState("joined");
      })
      .catch((err) => {
        setError(errorMessage(err));
        setState("error");
      });
  }, [token, refresh]);

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-sm rounded-2xl border border-slate-800 bg-slate-900/70 p-8 text-center shadow-xl">
        <div className="text-3xl">🌐</div>
        {state === "working" && <p className="mt-4 text-slate-300">Joining organization…</p>}
        {state === "joined" && (
          <>
            <h1 className="mt-4 text-xl font-bold">Welcome to {orgName}!</h1>
            <p className="mt-2 text-sm text-slate-400">
              You now have access to this organization's monitors and alerts.
            </p>
            <Link
              to="/"
              className="mt-6 inline-block rounded-lg bg-sky-500 px-5 py-2.5 font-medium text-white hover:bg-sky-400"
            >
              Go to dashboard
            </Link>
          </>
        )}
        {state === "error" && (
          <>
            <h1 className="mt-4 text-xl font-bold">Invitation not accepted</h1>
            <p className="mt-2 text-sm text-rose-400">{error}</p>
            <p className="mt-2 text-sm text-slate-400">
              Ask the person who invited you to send a new invitation.
            </p>
            <Link
              to="/"
              className="mt-6 inline-block rounded-lg border border-slate-700 px-5 py-2.5 text-slate-300 hover:bg-slate-800"
            >
              Go to dashboard
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
