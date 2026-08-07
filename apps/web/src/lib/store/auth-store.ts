import { create } from "zustand";
import { persist } from "zustand/middleware";
import { BaseLinkClient } from "@/lib/baselinker/client";

const DEFAULT_TOKEN = process.env.NEXT_PUBLIC_BL_DEFAULT_TOKEN ?? "";

interface AuthState {
  token: string;
  isAuthenticated: boolean;
  accountName: string;
  setToken: (token: string, accountName?: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: DEFAULT_TOKEN,
      isAuthenticated: !!DEFAULT_TOKEN,
      accountName: DEFAULT_TOKEN ? "Conta JRDEV1" : "",
      setToken: (token, accountName = "Minha Conta") => {
        BaseLinkClient.setToken(token);
        set({ token, isAuthenticated: !!token, accountName });
      },
      logout: () => {
        BaseLinkClient.setToken("");
        set({ token: "", isAuthenticated: false, accountName: "" });
      },
    }),
    { name: "jrdev1-auth" }
  )
);
