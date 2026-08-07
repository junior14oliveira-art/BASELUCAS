import { create } from "zustand";

interface UIState {
  sidebarCollapsed: boolean;
  sidebarMobileOpen: boolean;
  assistantOpen: boolean;
  activeModule: string;
  toggleSidebar: () => void;
  setSidebarMobileOpen: (open: boolean) => void;
  setAssistantOpen: (open: boolean) => void;
  toggleAssistant: () => void;
  setActiveModule: (module: string) => void;
}

export const useUIStore = create<UIState>((set) => ({
  sidebarCollapsed: false,
  sidebarMobileOpen: false,
  assistantOpen: false,
  activeModule: "dashboard",
  toggleSidebar: () =>
    set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setSidebarMobileOpen: (open) => set({ sidebarMobileOpen: open }),
  setAssistantOpen: (open) => set({ assistantOpen: open }),
  toggleAssistant: () => set((s) => ({ assistantOpen: !s.assistantOpen })),
  setActiveModule: (module) => set({ activeModule: module }),
}));
