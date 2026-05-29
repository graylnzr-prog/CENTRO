import { Show, SignInButton, UserButton } from "@clerk/nextjs";

export default function Home() {
  return (
    <main className="flex min-h-[calc(100vh-4rem)] items-center justify-center px-6 py-12">
      <section className="w-full max-w-4xl">
        <div className="grid gap-10 md:grid-cols-[1.15fr_0.85fr] md:items-center">
          <div className="space-y-6">
            <p className="text-sm font-medium uppercase text-zinc-500">
              Centro
            </p>
            <h1 className="max-w-2xl text-4xl font-semibold leading-tight text-zinc-950 sm:text-5xl">
              Sign in with Google and get back to your dashboard.
            </h1>
            <p className="max-w-xl text-lg leading-8 text-zinc-600">
              Clerk handles the secure Google authentication flow, sessions, and
              account controls for the app.
            </p>
            <Show when="signed-out">
              <SignInButton mode="redirect">
                <button className="inline-flex h-12 items-center justify-center gap-3 rounded-md border border-zinc-300 bg-white px-5 text-sm font-semibold text-zinc-900 shadow-sm transition hover:bg-zinc-100">
                  <span className="flex h-5 w-5 items-center justify-center rounded-full border border-zinc-300 text-xs font-bold">
                    G
                  </span>
                  Continue with Google
                </button>
              </SignInButton>
            </Show>
            <Show when="signed-in">
              <div className="flex items-center gap-3 rounded-md border border-zinc-200 bg-white p-4">
                <UserButton />
                <span className="text-sm font-medium text-zinc-700">
                  You are signed in.
                </span>
              </div>
            </Show>
          </div>
          <div className="rounded-md border border-zinc-200 bg-white p-6 shadow-sm">
            <div className="space-y-4">
              <div className="h-2 w-24 rounded-full bg-emerald-500" />
              <h2 className="text-xl font-semibold text-zinc-950">
                Google sign-in is ready for Clerk.
              </h2>
              <p className="leading-7 text-zinc-600">
                Add your Clerk keys, enable Google in the Clerk Dashboard, and
                users can authenticate from this entry point.
              </p>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
