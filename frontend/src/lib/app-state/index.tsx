"use client";

import { ActiveDatasetProvider } from "@/lib/app-state/active-dataset";
import { AppSessionProvider } from "@/lib/app-state/app-session";
import { DeveloperModeProvider } from "@/lib/app-state/developer-mode";
import { TaskQueueProvider } from "@/lib/app-state/task-queue";
import { ActiveTaskProvider } from "@/lib/app-state/active-task";
import { AppToastProvider } from "@/lib/app-state/toasts";

type AppStateProvidersProps = Readonly<{
  children: React.ReactNode;
}>;

export function AppStateProviders({ children }: AppStateProvidersProps) {
  return (
    <DeveloperModeProvider>
      <AppSessionProvider>
        <ActiveDatasetProvider>
          <AppToastProvider>
            <TaskQueueProvider>
              <ActiveTaskProvider>{children}</ActiveTaskProvider>
            </TaskQueueProvider>
          </AppToastProvider>
        </ActiveDatasetProvider>
      </AppSessionProvider>
    </DeveloperModeProvider>
  );
}

export { useActiveDataset } from "@/lib/app-state/active-dataset";
export { useAppSession } from "@/lib/app-state/app-session";
export { useTaskQueue } from "@/lib/app-state/task-queue";
export { useActiveTask } from "@/lib/app-state/active-task";
export { useDeveloperMode } from "@/lib/app-state/developer-mode";
export { useAppToasts } from "@/lib/app-state/toasts";
