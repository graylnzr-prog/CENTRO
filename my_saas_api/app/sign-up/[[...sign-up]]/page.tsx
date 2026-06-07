"use client";

import { useSignUp } from "@clerk/nextjs";

export default function SignUpPage() {
  const { fetchStatus, signUp } = useSignUp();

  const signUpWithGoogle = () => {
    if (fetchStatus === "fetching") {
      return;
    }

    void signUp.sso({
      strategy: "oauth_google",
      redirectUrl: "/",
      redirectCallbackUrl: "/sso-callback",
    });
  };

  return (
    <main className="flex min-h-[calc(100vh-4rem)] items-center justify-center px-6 py-12">
      <section className="w-full max-w-md rounded-md border border-zinc-200 bg-white p-6 shadow-sm">
        <div className="space-y-5">
          <div>
            <p className="text-sm font-medium uppercase text-zinc-500">
              Centro
            </p>
            <h1 className="mt-2 text-2xl font-semibold text-zinc-950">
              Continue with Google
            </h1>
          </div>
          <button
            className="inline-flex h-12 w-full items-center justify-center gap-3 rounded-md border border-zinc-300 bg-white px-5 text-sm font-semibold text-zinc-900 shadow-sm transition hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={fetchStatus === "fetching"}
            onClick={signUpWithGoogle}
            type="button"
          >
            <span className="flex h-5 w-5 items-center justify-center rounded-full border border-zinc-300 text-xs font-bold">
              G
            </span>
            Continue with Google
          </button>
        </div>
      </section>
    </main>
  );
}
