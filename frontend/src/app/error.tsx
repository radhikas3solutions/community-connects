"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/Button";
import { Container } from "@/components/ui/Container";

export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <Container className="py-24 text-center">
      <h1 className="text-2xl font-bold">Something went wrong · ఏదో పొరపాటు జరిగింది</h1>
      <Button onClick={reset} className="mt-6">
        Try again
      </Button>
    </Container>
  );
}
