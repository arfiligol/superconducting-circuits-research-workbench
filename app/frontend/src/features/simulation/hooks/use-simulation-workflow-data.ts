"use client";

import { useSimulationStageTaskData } from "@/features/simulation/hooks/use-simulation-stage-task-data";
import { useSimulationWorkflowContext } from "@/features/simulation/hooks/use-simulation-workflow-context";
import type { CircuitDefinitionId } from "@/features/circuit-definition-editor/lib/schema-identity";

export function useSimulationWorkflowData(
  selectedDefinitionId: CircuitDefinitionId | null,
  selectedTaskId: number | null,
) {
  const workflowContext = useSimulationWorkflowContext(
    selectedDefinitionId,
  );
  const stageTaskData = useSimulationStageTaskData({
    selectedTaskId,
    definitionId: workflowContext.resolvedDefinitionId,
    datasetId: workflowContext.activeDatasetState.activeDataset?.datasetId ?? null,
  });

  async function refreshSimulationWorkflow() {
    await Promise.all([
      workflowContext.refreshDefinitions(),
      workflowContext.refreshActiveDefinition(),
      stageTaskData.refreshTaskQueue().then(() => undefined),
      stageTaskData.refreshActiveTask(),
      stageTaskData.refreshUpstreamSimulationTask(),
      stageTaskData.refreshLatestSimulationTask(),
      stageTaskData.refreshLatestPostProcessingTask(),
      workflowContext.activeDatasetState.refreshActiveDataset(),
    ]);
  }

  return {
    session: workflowContext.session,
    activeDatasetState: workflowContext.activeDatasetState,
    taskQueueState: stageTaskData.taskQueueState,
    definitions: workflowContext.definitions,
    definitionsError: workflowContext.definitionsError,
    isDefinitionsLoading: workflowContext.isDefinitionsLoading,
    resolvedDefinitionId: workflowContext.resolvedDefinitionId,
    selectedDefinitionSummary: workflowContext.selectedDefinitionSummary,
    activeDefinition: workflowContext.activeDefinition,
    activeDefinitionError: workflowContext.activeDefinitionError,
    isDefinitionTransitioning: workflowContext.isDefinitionTransitioning,
    simulationTasks: stageTaskData.simulationTasks,
    currentContextSimulationTasks: stageTaskData.currentContextSimulationTasks,
    latestSimulationTask: stageTaskData.latestSimulationTask,
    latestSimulationStageTask: stageTaskData.latestSimulationStageTask,
    latestSimulationTaskDetail: stageTaskData.latestSimulationTaskDetail,
    attachedSimulationStageTask: stageTaskData.attachedSimulationStageTask,
    attachedSimulationTaskDetail: stageTaskData.attachedSimulationTaskDetail,
    latestSimulationTaskError: stageTaskData.latestSimulationTaskError,
    isLatestSimulationTaskLoading: stageTaskData.isLatestSimulationTaskLoading,
    latestPostProcessingTask: stageTaskData.latestPostProcessingTask,
    latestPostProcessingTaskDetail: stageTaskData.latestPostProcessingTaskDetail,
    latestPostProcessingTaskError: stageTaskData.latestPostProcessingTaskError,
    isLatestPostProcessingTaskLoading:
      stageTaskData.isLatestPostProcessingTaskLoading,
    resolvedTaskId: stageTaskData.resolvedTaskId,
    activeTask: stageTaskData.activeTask,
    activeTaskError: stageTaskData.activeTaskError,
    isTaskTransitioning: stageTaskData.isTaskTransitioning,
    refreshSimulationWorkflow,
    refreshDefinitions: workflowContext.refreshDefinitions,
    refreshTaskQueue: stageTaskData.refreshTaskQueue,
    refreshActiveTask: stageTaskData.refreshActiveTask,
  };
}
