import type { TaskDetail } from "@/lib/api/tasks";
import {
  buildTaskEventHistoryEntries,
  summarizeTaskEventHistory,
} from "@/lib/task-event-history";

import { SurfacePanel, SurfaceStat, SurfaceTag } from "./surface-kit";

type TaskEventHistoryPanelProps = Readonly<{
  title: string;
  description: string;
  task: TaskDetail | undefined;
  narrative: string;
  emptyMessage: string;
}>;

export function TaskEventHistoryPanel({
  title,
  description,
  task,
  narrative,
  emptyMessage,
}: TaskEventHistoryPanelProps) {
  const summary = summarizeTaskEventHistory(task);
  const entries = buildTaskEventHistoryEntries(task);

  return (
    <SurfacePanel title={title} description={description}>
      <div className="grid gap-3 md:grid-cols-4">
        <SurfaceStat label="Events" value={String(summary.total)} />
        <SurfaceStat
          label="Latest Event"
          value={summary.latestEventLabel ?? "--"}
          tone={summary.latestEventLabel ? "primary" : "default"}
        />
        <SurfaceStat label="Progress" value={summary.progressLabel ?? "--"} />
        <SurfaceStat
          label="Event State"
          value={summary.terminalStateLabel}
          tone={summary.errorCount > 0 ? "default" : "primary"}
        />
      </div>

      <div className="mt-4 rounded-[0.9rem] border border-border bg-surface px-4 py-4 text-sm text-muted-foreground">
        <p className="font-medium text-foreground">{narrative}</p>
        <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
          <SurfaceTag tone={summary.taskStatusLabel ? "primary" : "default"}>
            Task {summary.taskStatusLabel ?? "--"}
          </SurfaceTag>
          {summary.dispatchStatusLabel ? (
            <SurfaceTag tone="default">Dispatch {summary.dispatchStatusLabel}</SurfaceTag>
          ) : null}
          <SurfaceTag tone={summary.warningCount > 0 ? "warning" : "default"}>
            Warning events {summary.warningCount}
          </SurfaceTag>
          <SurfaceTag tone={summary.errorCount > 0 ? "warning" : "default"}>
            Error events {summary.errorCount}
          </SurfaceTag>
          <SurfaceTag tone="default">Info events {summary.infoCount}</SurfaceTag>
          {summary.latestOccurredAt ? (
            <SurfaceTag tone="default">Latest {summary.latestOccurredAt}</SurfaceTag>
          ) : null}
        </div>
      </div>

      {entries.length > 0 ? (
        <div className="mt-4 space-y-3">
          {entries.map((entry) => (
            <div
              key={entry.eventKey}
              className="rounded-[0.9rem] border border-border bg-surface px-4 py-4"
            >
              <div className="flex flex-wrap items-center gap-2 text-[11px]">
                <SurfaceTag tone={entry.eventTone}>{entry.eventTypeLabel}</SurfaceTag>
                <SurfaceTag tone={entry.levelTone}>{entry.level}</SurfaceTag>
                <SurfaceTag tone="default">{entry.occurredAt}</SurfaceTag>
              </div>
              <p className="mt-3 text-sm font-semibold text-foreground">{entry.message}</p>
              {entry.metadataEntries.length > 0 ? (
                <div className="mt-3 grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
                  {entry.metadataEntries.map((metadata) => (
                    <div key={`${entry.eventKey}-${metadata.key}`}>
                      <span className="text-foreground">{metadata.label}:</span> {metadata.value}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="mt-3 text-xs text-muted-foreground">
                  No additional persisted metadata was recorded for this event.
                </p>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="mt-4 rounded-[0.9rem] border border-dashed border-border bg-surface px-4 py-4 text-sm text-muted-foreground">
          {emptyMessage}
        </div>
      )}
    </SurfacePanel>
  );
}
