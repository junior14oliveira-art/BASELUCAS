import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "JRDEV1 — Gestão de E-commerce",
  description: "Sistema completo de gestão: pedidos, estoque, filas PickPack e muito mais.",
};

// Aplica o tema visual salvo ANTES da primeira pintura (evita "piscada").
// A escolha fica em localStorage sob "jrdev1_skin" ("classico" | "moderno").
const skinBootstrap = `
try {
  if (localStorage.getItem("jrdev1_skin") === "moderno") {
    document.documentElement.classList.add("theme-moderno");
  }
} catch (e) {}
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: skinBootstrap }} />
      </head>
      <body className={inter.className}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
