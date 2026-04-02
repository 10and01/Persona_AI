import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Persona Studio",
  description: "Realtime 3-layer memory and persona preview",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
