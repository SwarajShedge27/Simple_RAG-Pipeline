"use client";

import { TracewayProvider as Traceway } from "@tracewayapp/react";

const connectionString = process.env.NEXT_PUBLIC_TRACEWAY_CONNECTION_STRING;

export default function TracewayProvider({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  if (!connectionString) {
    return children;
  }

  return <Traceway connectionString={connectionString}>{children}</Traceway>;
}