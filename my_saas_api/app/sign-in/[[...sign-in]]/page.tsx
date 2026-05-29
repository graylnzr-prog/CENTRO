import { SignIn } from "@clerk/nextjs";

export default function SignInPage() {
  return (
    <main className="flex min-h-[calc(100vh-4rem)] items-center justify-center px-6 py-12">
      <SignIn
        appearance={{
          elements: {
            rootBox: "mx-auto",
            cardBox: "shadow-sm border border-zinc-200",
          },
        }}
        fallbackRedirectUrl="/"
        signUpUrl="/sign-up"
      />
    </main>
  );
}
