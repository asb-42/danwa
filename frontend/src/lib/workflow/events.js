/**
 * Workflow Event Type Definitions (JSDoc)
 *
 * Every state change in the workflow is emitted as a typed event.
 * The visualization subscribes to these events and mutates the graph accordingly.
 */

/**
 * @typedef {'AGENT_STARTED'|'AGENT_COMPLETED'|'ARTIFACT_PRODUCED'|
 *   'USER_CLARIFICATION_REQUESTED'|'USER_CLARIFICATION_RECEIVED'|
 *   'FEEDBACK_LOOP_INITIATED'|'USER_OUT_OF_BAND_INPUT'|
 *   'ROUND_COMPLETED'|'WORKFLOW_COMPLETED'|'OOB_CONSUMED'} WorkflowEventType
 */

/**
 * @typedef {Object} AgentStartedEvent
 * @property {'AGENT_STARTED'} type
 * @property {{ agentId: string, role: string, round: number,
 *   inputArtifactIds: string[], timestamp: number }} payload
 */

/**
 * @typedef {Object} AgentCompletedEvent
 * @property {'AGENT_COMPLETED'} type
 * @property {{ agentId: string, role: string, round: number,
 *   outputArtifactId: string, durationMs: number,
 *   nextAgentId?: string, decision?: 'proceed'|'retry'|'request_clarification' }} payload
 */

/**
 * @typedef {Object} ArtifactProducedEvent
 * @property {'ARTIFACT_PRODUCED'} type
 * @property {{ artifactId: string, type: 'strategy'|'critique'|'synthesis'|'consensus',
 *   producerAgentId: string, round: number, summary: string, tokenCount: number }} payload
 */

/**
 * @typedef {Object} UserClarificationRequestedEvent
 * @property {'USER_CLARIFICATION_REQUESTED'} type
 * @property {{ requestId: string, requestingAgentId: string,
 *   requestingAgentRole: string, question: string,
 *   blocking: boolean, round: number }} payload
 */

/**
 * @typedef {Object} UserClarificationReceivedEvent
 * @property {'USER_CLARIFICATION_RECEIVED'} type
 * @property {{ requestId: string, response: string,
 *   respondingToAgentId: string, round: number }} payload
 */

/**
 * @typedef {Object} FeedbackLoopInitiatedEvent
 * @property {'FEEDBACK_LOOP_INITIATED'} type
 * @property {{ loopId: string, fromAgentId: string, toAgentId: string,
 *   reason: string, round: number, iteration: number }} payload
 */

/**
 * @typedef {Object} UserOutOfBandInputEvent
 * @property {'USER_OUT_OF_BAND_INPUT'} type
 * @property {{ inputId: string, targetAgentId: string,
 *   content: string, round: number }} payload
 */

/**
 * @typedef {Object} RoundCompletedEvent
 * @property {'ROUND_COMPLETED'} type
 * @property {{ round: number, finalArtifactId: string,
 *   pathTaken: string[] }} payload
 */

/**
 * @typedef {Object} WorkflowCompletedEvent
 * @property {'WORKFLOW_COMPLETED'} type
 * @property {{ finalConsensusId: string, totalRounds: number,
 *   totalDurationMs: number }} payload
 */

/**
 * @typedef {Object} OOBConsumedEvent
 * @property {'OOB_CONSUMED'} type
 * @property {{ oobIds: string[], byAgentId: string }} payload
 */

/**
 * @typedef {AgentStartedEvent|AgentCompletedEvent|ArtifactProducedEvent|
 *   UserClarificationRequestedEvent|UserClarificationReceivedEvent|
 *   FeedbackLoopInitiatedEvent|UserOutOfBandInputEvent|
 *   RoundCompletedEvent|WorkflowCompletedEvent|OOBConsumedEvent} WorkflowEvent
 */
