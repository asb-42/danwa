# API Reference — Debate-Agent

> **Version**: 1.1.0

---

## Table of Contents

- [a2a](#a2a)
- [a2a-discovery](#a2a-discovery)
- [audit](#audit)
- [blueprint-events](#blueprint-events)
- [blueprints](#blueprints)
- [canvas](#canvas)
- [config](#config)
- [debate](#debate)
- [dms](#dms)
- [health](#health)
- [hitl](#hitl)
- [i18n](#i18n)
- [input-composer](#input-composer)
- [modules](#modules)
- [optimization-proposals](#optimization-proposals)
- [output-composer](#output-composer)
- [profiles](#profiles)
- [projects](#projects)
- [reports](#reports)
- [sessions](#sessions)
- [system](#system)
- [tone-profiles](#tone-profiles)
- [translation](#translation)
- [workflow-exec](#workflow-exec)
- [workflow-templates](#workflow-templates)

---

## Data Models

- [A2AAgentConfig](#data-model-a2aagentconfig)
- [AgentBlueprint](#data-model-agentblueprint)
- [AgentBundle](#data-model-agentbundle)
- [AgentConfig](#data-model-agentconfig)
- [AgentOutput](#data-model-agentoutput)
- [AgentPersona](#data-model-agentpersona)
- [ApproveResponse](#data-model-approveresponse)
- [ApproveTranslationRequest](#data-model-approvetranslationrequest)
- [BackupCreateBody](#data-model-backupcreatebody)
- [BackupRestoreBody](#data-model-backuprestorebody)
- [BackupSettingsBody](#data-model-backupsettingsbody)
- [BatchTranslateRequest](#data-model-batchtranslaterequest)
- [BlueprintLLMProfile](#data-model-blueprintllmprofile)
- [Body_upload_document_api_v1_dms_documents_post](#data-model-body_upload_document_api_v1_dms_documents_post)
- [BulkTranslateRequest](#data-model-bulktranslaterequest)
- [BulkTranslationRequest](#data-model-bulktranslationrequest)
- [CanvasLayout-Input](#data-model-canvaslayout-input)
- [CanvasLayout-Output](#data-model-canvaslayout-output)
- [CanvasLayoutData](#data-model-canvaslayoutdata)
- [CanvasLayoutEdge](#data-model-canvaslayoutedge)
- [CanvasLayoutNode](#data-model-canvaslayoutnode)
- [CanvasLayoutViewport](#data-model-canvaslayoutviewport)
- [CapabilitiesRequest](#data-model-capabilitiesrequest)
- [CaseInput](#data-model-caseinput)
- [CompilationResult](#data-model-compilationresult)
- [ConditionalEdge](#data-model-conditionaledge)
- [ConvertToWorkflowRequest](#data-model-converttoworkflowrequest)
- [CreatePromptVariantRequest](#data-model-createpromptvariantrequest)
- [CreateRenderRequest](#data-model-createrenderrequest)
- [CreateRenderResponse](#data-model-createrenderresponse)
- [CreateReportRequest](#data-model-createreportrequest)
- [CreateReportResponse](#data-model-createreportresponse)
- [DebateContinueBody](#data-model-debatecontinuebody)
- [DebateListItem](#data-model-debatelistitem)
- [DebateRequest](#data-model-debaterequest)
- [DebateResponse](#data-model-debateresponse)
- [DebateStatus](#data-model-debatestatus)
- [DebateStatusResponse](#data-model-debatestatusresponse)
- [DiscoverRequest](#data-model-discoverrequest)
- [DocumentAssignment](#data-model-documentassignment)
- [DuplicateRequest](#data-model-duplicaterequest)
- [ExtensionDecision](#data-model-extensiondecision)
- [ExtensionDecisionModel](#data-model-extensiondecisionmodel)
- [ExtensionRequest](#data-model-extensionrequest)
- [ExtensionResponse](#data-model-extensionresponse)
- [ForkDebateBody](#data-model-forkdebatebody)
- [ForkFromConsensusBody](#data-model-forkfromconsensusbody)
- [HITLMode](#data-model-hitlmode)
- [HITLStatusResponse](#data-model-hitlstatusresponse)
- [HTTPValidationError](#data-model-httpvalidationerror)
- [HealthResponse](#data-model-healthresponse)
- [ImportBundleRequest](#data-model-importbundlerequest)
- [ImportResult](#data-model-importresult)
- [InjectRequest](#data-model-injectrequest)
- [InjectResponse](#data-model-injectresponse)
- [InputJobStatusResponse](#data-model-inputjobstatusresponse)
- [InputPluginInfo](#data-model-inputplugininfo)
- [InstallRequest](#data-model-installrequest)
- [InstantiateRequest](#data-model-instantiaterequest)
- [InteractionDirection](#data-model-interactiondirection)
- [InteractionListResponse](#data-model-interactionlistresponse)
- [InteractionResponse](#data-model-interactionresponse)
- [InteractionStatus](#data-model-interactionstatus)
- [InteractionType](#data-model-interactiontype)
- [InterjectRequest](#data-model-interjectrequest)
- [InterjectResponse](#data-model-interjectresponse)
- [InterjectionPoint](#data-model-interjectionpoint)
- [InterruptInfo](#data-model-interruptinfo)
- [InterruptStatus](#data-model-interruptstatus)
- [InvalidateTranslationRequest](#data-model-invalidatetranslationrequest)
- [LLMProfile](#data-model-llmprofile)
- [LLMProvider](#data-model-llmprovider)
- [LanguageBody](#data-model-languagebody)
- [LanguagePackExportRequest](#data-model-languagepackexportrequest)
- [LaunchWorkflowRequest](#data-model-launchworkflowrequest)
- [LaunchWorkflowResponse](#data-model-launchworkflowresponse)
- [OOBInputBody](#data-model-oobinputbody)
- [OOBInputResponse](#data-model-oobinputresponse)
- [OOBTarget](#data-model-oobtarget)
- [OOBTargetType](#data-model-oobtargettype)
- [PauseAction](#data-model-pauseaction)
- [PauseRequest](#data-model-pauserequest)
- [PauseResponse](#data-model-pauseresponse)
- [PluginInfo](#data-model-plugininfo)
- [ProfileUpdateRequest](#data-model-profileupdaterequest)
- [ProjectConfig-Input](#data-model-projectconfig-input)
- [ProjectConfig-Output](#data-model-projectconfig-output)
- [ProjectConfigUpdateRequest](#data-model-projectconfigupdaterequest)
- [ProjectCreateRequest](#data-model-projectcreaterequest)
- [ProjectListItem](#data-model-projectlistitem)
- [ProjectResponse](#data-model-projectresponse)
- [ProjectUpdateRequest](#data-model-projectupdaterequest)
- [PromptTemplate](#data-model-prompttemplate)
- [PromptVariant](#data-model-promptvariant)
- [ProposalResponse](#data-model-proposalresponse)
- [ReflectResponse](#data-model-reflectresponse)
- [RegisterLocaleRequest](#data-model-registerlocalerequest)
- [RenderJobStatusResponse](#data-model-renderjobstatusresponse)
- [ReportStatusResponse](#data-model-reportstatusresponse)
- [ResolvedAgent](#data-model-resolvedagent)
- [ResolvedBundle](#data-model-resolvedbundle)
- [RespondRequest](#data-model-respondrequest)
- [RespondResponse](#data-model-respondresponse)
- [RoleDefinition](#data-model-roledefinition)
- [RoleType](#data-model-roletype)
- [RoundData](#data-model-rounddata)
- [SearchMode](#data-model-searchmode)
- [SessionStateResponse](#data-model-sessionstateresponse)
- [StartFromLayoutBody](#data-model-startfromlayoutbody)
- [StartFromWorkflowBody](#data-model-startfromworkflowbody)
- [StartWorkflowRequest](#data-model-startworkflowrequest)
- [StartWorkflowResponse](#data-model-startworkflowresponse)
- [StatusResponse](#data-model-statusresponse)
- [SubmitInputRequest](#data-model-submitinputrequest)
- [SubmitInputResponse](#data-model-submitinputresponse)
- [TemplatePlaceholder](#data-model-templateplaceholder)
- [TerminationCondition](#data-model-terminationcondition)
- [ToneProfile](#data-model-toneprofile)
- [TranslatePromptRequest](#data-model-translatepromptrequest)
- [TranslationSetRequest](#data-model-translationsetrequest)
- [UninstallRequest](#data-model-uninstallrequest)
- [UtilityLLMRequest](#data-model-utilityllmrequest)
- [ValidateRequest](#data-model-validaterequest)
- [ValidationError](#data-model-validationerror)
- [WorkflowDefinition](#data-model-workflowdefinition)
- [WorkflowEdge](#data-model-workflowedge)
- [WorkflowNode](#data-model-workflownode)
- [WorkflowTemplate](#data-model-workflowtemplate)
- [backend__api__routers__modules__TranslateRequest](#data-model-backend__api__routers__modules__translaterequest)
- [backend__api__routers__translation__TranslateRequest](#data-model-backend__api__routers__translation__translaterequest)

---

## a2a

### `GET` `/.well-known/agent.json`

**Get Agent Card**

A2A Agent Card — discovery endpoint.

Returns the Agent Card JSON so external A2A clients can discover
Danwa's capabilities, available projects, and supported languages.

*Operation ID*: `get_agent_card__well_known_agent_json_get`

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |

---

### `POST` `/a2a`

**Handle A2A Request**

A2A JSON-RPC endpoint — handles all A2A methods.

Supported methods:
- ``tasks/send`` — create and start a debate
- ``tasks/get`` — poll for task status/result
- ``tasks/cancel`` — cancel a running task

*Operation ID*: `handle_a2a_request_a2a_post`

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |

---

## a2a-discovery

### `POST` `/api/v1/a2a/capabilities/{profile_id}`

**Store A2A Capabilities**

Store discovered A2A capabilities in a blueprint LLM profile.

Args:
    profile_id: The blueprint LLM profile ID to update.
    body: The discovered capabilities.

Returns:
    Dict with status and profile_id.

Raises:
    HTTP 404: Profile not found.

*Operation ID*: `store_a2a_capabilities_api_v1_a2a_capabilities__profile_id__post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `profile_id` | path | string | ✓ |  |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/a2a/capabilities/{profile_id}`

**Store A2A Capabilities**

Store discovered A2A capabilities in a blueprint LLM profile.

Args:
    profile_id: The blueprint LLM profile ID to update.
    body: The discovered capabilities.

Returns:
    Dict with status and profile_id.

Raises:
    HTTP 404: Profile not found.

*Operation ID*: `store_a2a_capabilities_api_v1_a2a_capabilities__profile_id__post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `profile_id` | path | string | ✓ |  |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/a2a/discover`

**Discover A2A Agent**

Discover the capabilities of an external A2A agent.

Fetches the agent's Agent Card and returns structured capability info.

Returns:
    Dict with name, description, version, capabilities, skills,
    input_modes, output_modes.

Raises:
    HTTP 400: Invalid URL format.
    HTTP 403: Private IP blocked.
    HTTP 502: Agent unreachable.
    HTTP 504: Discovery timed out.

*Operation ID*: `discover_a2a_agent_api_v1_a2a_discover_post`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/a2a/discover`

**Discover A2A Agent**

Discover the capabilities of an external A2A agent.

Fetches the agent's Agent Card and returns structured capability info.

Returns:
    Dict with name, description, version, capabilities, skills,
    input_modes, output_modes.

Raises:
    HTTP 400: Invalid URL format.
    HTTP 403: Private IP blocked.
    HTTP 502: Agent unreachable.
    HTTP 504: Discovery timed out.

*Operation ID*: `discover_a2a_agent_api_v1_a2a_discover_post`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

## audit

### `GET` `/api/v1/audit/project/{project_id}`

**Get Audit Events By Project**

Return audit events for a project, ordered by timestamp desc.

*Operation ID*: `get_audit_events_by_project_api_v1_audit_project__project_id__get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `project_id` | path | string | ✓ |  |
| `limit` | query | integer |  |  |
| `offset` | query | integer |  |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/audit/{debate_id_or_title}`

**Get Audit Events**

Return all audit events for a debate, ordered by round.

Accepts either a debate UUID or a debate title as the path parameter.
If a title is provided, it is resolved to the matching debate ID first.

Events are enriched with actual agent output content from the debate store.

*Operation ID*: `get_audit_events_api_v1_audit__debate_id_or_title__get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `debate_id_or_title` | path | string | ✓ |  |
| `X-Project-Id` | header | string | ✓ | Active project UUID |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

## blueprint-events

### `GET` `/api/v1/blueprint-events/stream`

**Stream Blueprint Events**

SSE endpoint for real-time blueprint/canvas updates.

If ``session_id`` is provided, subscribes to the event bus for that
workflow session and yields workflow-specific events (node updates,
completion, errors, interjections, etc.).

If no ``session_id`` is provided, falls back to a keep-alive stream
for general canvas updates.

*Operation ID*: `stream_blueprint_events_api_v1_blueprint_events_stream_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `session_id` | query | string |  | Workflow session ID to subscribe to |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

## blueprints

### `GET` `/api/v1/blueprints/agent-blueprints`

**List Agent Blueprints**

List agent blueprints with optional active-only filter and pagination.

*Operation ID*: `list_agent_blueprints_api_v1_blueprints_agent_blueprints_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `active_only` | query | boolean |  |  |
| `limit` | query | integer |  |  |
| `offset` | query | integer |  |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/blueprints/agent-blueprints`

**Create Agent Blueprint**

Create a new agent blueprint.

*Operation ID*: `create_agent_blueprint_api_v1_blueprints_agent_blueprints_post`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `201` | Successful Response |
| `422` | Validation Error |

---

### `DELETE` `/api/v1/blueprints/agent-blueprints/{blueprint_id}`

**Delete Agent Blueprint**

Delete an agent blueprint.

*Operation ID*: `delete_agent_blueprint_api_v1_blueprints_agent_blueprints__blueprint_id__delete`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `blueprint_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/blueprints/agent-blueprints/{blueprint_id}`

**Get Agent Blueprint**

Get a single agent blueprint by ID.

*Operation ID*: `get_agent_blueprint_api_v1_blueprints_agent_blueprints__blueprint_id__get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `blueprint_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `PUT` `/api/v1/blueprints/agent-blueprints/{blueprint_id}`

**Update Agent Blueprint**

Update an existing agent blueprint.

*Operation ID*: `update_agent_blueprint_api_v1_blueprints_agent_blueprints__blueprint_id__put`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `blueprint_id` | path | string | ✓ |  |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/blueprints/argumentation-patterns`

**List Argumentation Patterns**

List all available argumentation pattern names, including enabled module patterns.

*Operation ID*: `list_argumentation_patterns_api_v1_blueprints_argumentation_patterns_get`

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |

---

### `GET` `/api/v1/blueprints/argumentation-patterns/{name}`

**Get Argumentation Pattern**

Get all role prompts for a given argumentation pattern.

Returns a mapping of role_type_id → prompt content string.

*Operation ID*: `get_argumentation_pattern_api_v1_blueprints_argumentation_patterns__name__get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `name` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/blueprints/bundles`

**List Bundles**

List agent bundles with optional active-only filter and pagination, including enabled module bundles.

*Operation ID*: `list_bundles_api_v1_blueprints_bundles_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `active_only` | query | boolean |  |  |
| `limit` | query | integer |  |  |
| `offset` | query | integer |  |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/blueprints/bundles`

**Create Bundle**

Create a new agent bundle.

Validates that all referenced entities (LLM profile, RoleType, etc.) exist.

*Operation ID*: `create_bundle_api_v1_blueprints_bundles_post`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `201` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/blueprints/bundles/import`

**Import Bundle Endpoint**

Import a bundle from an exported JSON document.

Conflict strategies:
- ``skip``: Skip entities that already exist by ID.
- ``overwrite``: Replace existing entities.
- ``rename``: Generate new IDs for conflicts (default).

*Operation ID*: `import_bundle_endpoint_api_v1_blueprints_bundles_import_post`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `201` | Successful Response |
| `422` | Validation Error |

---

### `DELETE` `/api/v1/blueprints/bundles/{bundle_id}`

**Delete Bundle**

Delete an agent bundle.

*Operation ID*: `delete_bundle_api_v1_blueprints_bundles__bundle_id__delete`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `bundle_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/blueprints/bundles/{bundle_id}`

**Get Bundle**

Get a single agent bundle by ID.

*Operation ID*: `get_bundle_api_v1_blueprints_bundles__bundle_id__get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `bundle_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `PUT` `/api/v1/blueprints/bundles/{bundle_id}`

**Update Bundle**

Update an existing agent bundle.

*Operation ID*: `update_bundle_api_v1_blueprints_bundles__bundle_id__put`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `bundle_id` | path | string | ✓ |  |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/blueprints/bundles/{bundle_id}/export`

**Export Bundle Endpoint**

Export a bundle as a portable JSON document with all dependencies.

*Operation ID*: `export_bundle_endpoint_api_v1_blueprints_bundles__bundle_id__export_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `bundle_id` | path | string | ✓ |  |
| `include_all_role_types` | query | boolean |  |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/blueprints/bundles/{bundle_id}/resolve`

**Resolve Bundle Endpoint**

Resolve a bundle — load all referenced entities and assemble system prompt.

*Operation ID*: `resolve_bundle_endpoint_api_v1_blueprints_bundles__bundle_id__resolve_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `bundle_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/blueprints/import`

**Run Import**

Trigger an idempotent import of all blueprint entities.

Accepts optional ``{"dry_run": true}`` to preview without persisting.

*Operation ID*: `run_import_api_v1_blueprints_import_post`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/blueprints/llm-profiles`

**List Llm Profiles**

List all LLM profiles with pagination, including enabled module profiles.

*Operation ID*: `list_llm_profiles_api_v1_blueprints_llm_profiles_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `limit` | query | integer |  |  |
| `offset` | query | integer |  |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/blueprints/llm-profiles`

**Create Llm Profile**

Create a new LLM profile.

*Operation ID*: `create_llm_profile_api_v1_blueprints_llm_profiles_post`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `201` | Successful Response |
| `422` | Validation Error |

---

### `DELETE` `/api/v1/blueprints/llm-profiles/{profile_id}`

**Delete Llm Profile**

Delete an LLM profile.

*Operation ID*: `delete_llm_profile_api_v1_blueprints_llm_profiles__profile_id__delete`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `profile_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/blueprints/llm-profiles/{profile_id}`

**Get Llm Profile**

Get a single LLM profile by ID.

*Operation ID*: `get_llm_profile_api_v1_blueprints_llm_profiles__profile_id__get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `profile_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `PUT` `/api/v1/blueprints/llm-profiles/{profile_id}`

**Update Llm Profile**

Update an existing LLM profile.

*Operation ID*: `update_llm_profile_api_v1_blueprints_llm_profiles__profile_id__put`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `profile_id` | path | string | ✓ |  |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/blueprints/prompt-templates`

**List Prompt Templates**

List prompt templates with optional filtering and pagination, including enabled module prompts.

*Operation ID*: `list_prompt_templates_api_v1_blueprints_prompt_templates_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `role` | query | string |  |  |
| `variant` | query | string |  |  |
| `limit` | query | integer |  |  |
| `offset` | query | integer |  |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/blueprints/prompt-templates`

**Create Prompt Template**

Create a new prompt template.

*Operation ID*: `create_prompt_template_api_v1_blueprints_prompt_templates_post`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `201` | Successful Response |
| `422` | Validation Error |

---

### `DELETE` `/api/v1/blueprints/prompt-templates/{template_id}`

**Delete Prompt Template**

Delete a prompt template.

*Operation ID*: `delete_prompt_template_api_v1_blueprints_prompt_templates__template_id__delete`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `template_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/blueprints/prompt-templates/{template_id}`

**Get Prompt Template**

Get a single prompt template by ID.

*Operation ID*: `get_prompt_template_api_v1_blueprints_prompt_templates__template_id__get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `template_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `PUT` `/api/v1/blueprints/prompt-templates/{template_id}`

**Update Prompt Template**

Update an existing prompt template.

*Operation ID*: `update_prompt_template_api_v1_blueprints_prompt_templates__template_id__put`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `template_id` | path | string | ✓ |  |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/blueprints/role-definitions`

**List Role Definitions**

List role definitions with optional filtering and pagination, including enabled module personas.

*Operation ID*: `list_role_definitions_api_v1_blueprints_role_definitions_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `role` | query | string |  |  |
| `argumentation_pattern` | query | string |  |  |
| `limit` | query | integer |  |  |
| `offset` | query | integer |  |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/blueprints/role-definitions`

**Create Role Definition**

Create a new role definition.

*Operation ID*: `create_role_definition_api_v1_blueprints_role_definitions_post`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `201` | Successful Response |
| `422` | Validation Error |

---

### `DELETE` `/api/v1/blueprints/role-definitions/{role_id}`

**Delete Role Definition**

Delete a role definition.

*Operation ID*: `delete_role_definition_api_v1_blueprints_role_definitions__role_id__delete`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `role_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/blueprints/role-definitions/{role_id}`

**Get Role Definition**

Get a single role definition by ID.

*Operation ID*: `get_role_definition_api_v1_blueprints_role_definitions__role_id__get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `role_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `PUT` `/api/v1/blueprints/role-definitions/{role_id}`

**Update Role Definition**

Update an existing role definition.

*Operation ID*: `update_role_definition_api_v1_blueprints_role_definitions__role_id__put`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `role_id` | path | string | ✓ |  |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/blueprints/role-types`

**List Role Types**

List all role types with pagination, including enabled module role types.

*Operation ID*: `list_role_types_api_v1_blueprints_role_types_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `limit` | query | integer |  |  |
| `offset` | query | integer |  |  |
| `active_only` | query | boolean |  |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/blueprints/role-types`

**Create Role Type**

Create a new role type.

*Operation ID*: `create_role_type_api_v1_blueprints_role_types_post`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `201` | Successful Response |
| `422` | Validation Error |

---

### `DELETE` `/api/v1/blueprints/role-types/{role_type_id}`

**Delete Role Type**

Delete a role type.

*Operation ID*: `delete_role_type_api_v1_blueprints_role_types__role_type_id__delete`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `role_type_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/blueprints/role-types/{role_type_id}`

**Get Role Type**

Get a single role type by ID.

*Operation ID*: `get_role_type_api_v1_blueprints_role_types__role_type_id__get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `role_type_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `PUT` `/api/v1/blueprints/role-types/{role_type_id}`

**Update Role Type**

Update an existing role type.

*Operation ID*: `update_role_type_api_v1_blueprints_role_types__role_type_id__put`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `role_type_id` | path | string | ✓ |  |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/blueprints/workflows`

**List Workflow Definitions**

List all workflow definitions with pagination.

*Operation ID*: `list_workflow_definitions_api_v1_blueprints_workflows_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `limit` | query | integer |  |  |
| `offset` | query | integer |  |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/blueprints/workflows`

**Create Workflow Definition**

Create a new workflow definition.

*Operation ID*: `create_workflow_definition_api_v1_blueprints_workflows_post`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `201` | Successful Response |
| `422` | Validation Error |

---

### `DELETE` `/api/v1/blueprints/workflows/{wf_id}`

**Delete Workflow Definition**

Delete a workflow definition.

*Operation ID*: `delete_workflow_definition_api_v1_blueprints_workflows__wf_id__delete`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `wf_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/blueprints/workflows/{wf_id}`

**Get Workflow Definition**

Get a single workflow definition by ID.

*Operation ID*: `get_workflow_definition_api_v1_blueprints_workflows__wf_id__get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `wf_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `PUT` `/api/v1/blueprints/workflows/{wf_id}`

**Update Workflow Definition**

Update an existing workflow definition.

*Operation ID*: `update_workflow_definition_api_v1_blueprints_workflows__wf_id__put`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `wf_id` | path | string | ✓ |  |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/blueprints/workflows/{wf_id}/clone`

**Clone Workflow**

Clone a workflow definition.

Creates a deep copy with a new ID, incremented version, and
``is_locked=False``.

*Operation ID*: `clone_workflow_api_v1_blueprints_workflows__wf_id__clone_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `wf_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `201` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/blueprints/workflows/{wf_id}/compile`

**Compile Workflow**

Compile a workflow definition — validate blueprint references.

*Operation ID*: `compile_workflow_api_v1_blueprints_workflows__wf_id__compile_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `wf_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/blueprints/workflows/{wf_id}/save-as-template`

**Save Workflow As Template**

Create a custom template from an existing WorkflowDefinition.

Request body: ``{"name": "...", "description": "...", "extracted_placeholders": ["key1"]}``

Fields listed in ``extracted_placeholders`` are replaced with
``{{key}}`` placeholders in the template data.

*Operation ID*: `save_workflow_as_template_api_v1_blueprints_workflows__wf_id__save_as_template_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `wf_id` | path | string | ✓ |  |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `201` | Successful Response |
| `422` | Validation Error |

---

## canvas

### `GET` `/api/v1/canvas/layouts`

**List Layouts**

List canvas layouts with optional project filter and pagination.

*Operation ID*: `list_layouts_api_v1_canvas_layouts_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `project_id` | query | string |  |  |
| `limit` | query | integer |  |  |
| `offset` | query | integer |  |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/canvas/layouts`

**Create Layout**

Create a new canvas layout.

*Operation ID*: `create_layout_api_v1_canvas_layouts_post`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `201` | Successful Response |
| `422` | Validation Error |

---

### `DELETE` `/api/v1/canvas/layouts/{layout_id}`

**Delete Layout**

Delete a canvas layout.

*Operation ID*: `delete_layout_api_v1_canvas_layouts__layout_id__delete`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `layout_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/canvas/layouts/{layout_id}`

**Get Layout**

Get a single canvas layout by ID.

*Operation ID*: `get_layout_api_v1_canvas_layouts__layout_id__get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `layout_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `PUT` `/api/v1/canvas/layouts/{layout_id}`

**Update Layout**

Update an existing canvas layout.

*Operation ID*: `update_layout_api_v1_canvas_layouts__layout_id__put`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `layout_id` | path | string | ✓ |  |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/canvas/layouts/{layout_id}/to-workflow`

**Convert Layout To Workflow**

Convert a canvas layout to a WorkflowDefinition and persist it.

Takes the canvas layout's ``layout_data`` (nodes + edges with positions)
and transforms it into a structured ``WorkflowDefinition`` with typed
nodes, edges, entry point, and termination conditions.

The resulting WorkflowDefinition is saved to the repository and can then
be compiled and executed via ``POST /workflow-exec/{wf_id}/start``.

*Operation ID*: `convert_layout_to_workflow_api_v1_canvas_layouts__layout_id__to_workflow_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `layout_id` | path | string | ✓ |  |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `201` | Successful Response |
| `422` | Validation Error |

---

## config

### `POST` `/api/v1/config/backup`

**Create Backup**

Create a new backup archive.

Creates a ZIP file containing all critical user data
(projects, audit DB, configs, etc.).

*Operation ID*: `create_backup_api_v1_config_backup_post`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/config/backup-settings`

**Get Backup Settings**

Get current backup settings.

*Operation ID*: `get_backup_settings_api_v1_config_backup_settings_get`

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |

---

### `PUT` `/api/v1/config/backup-settings`

**Update Backup Settings**

Update backup settings.

*Operation ID*: `update_backup_settings_api_v1_config_backup_settings_put`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/config/backups`

**List Backups**

List all available backups with metadata.

*Operation ID*: `list_backups_api_v1_config_backups_get`

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |

---

### `DELETE` `/api/v1/config/backups/{backup_id}`

**Delete Backup**

Delete a backup archive.

*Operation ID*: `delete_backup_api_v1_config_backups__backup_id__delete`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `backup_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/config/backups/{backup_id}`

**Get Backup**

Get metadata for a specific backup.

*Operation ID*: `get_backup_api_v1_config_backups__backup_id__get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `backup_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/config/backups/{backup_id}/files`

**List Backup Files**

List all files contained in a backup.

*Operation ID*: `list_backup_files_api_v1_config_backups__backup_id__files_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `backup_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/config/backups/{backup_id}/restore`

**Restore Backup**

Restore data from a backup.

.. warning::
    This is a DESTRUCTIVE operation — it will overwrite existing data.

*Operation ID*: `restore_backup_api_v1_config_backups__backup_id__restore_post`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/config/backups/{backup_id}/verify`

**Verify Backup**

Verify the integrity of a backup.

Checks the ZIP structure and validates SHA-256 checksums.

*Operation ID*: `verify_backup_api_v1_config_backups__backup_id__verify_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `backup_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/config/language`

**Get Language**

Get the current UI language.

*Operation ID*: `get_language_api_v1_config_language_get`

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |

---

### `PUT` `/api/v1/config/language`

**Set Language**

Set the UI language.

*Operation ID*: `set_language_api_v1_config_language_put`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/config/service-llm`

**Get Utility Llm Config**

Get the current utility LLM configuration.

*Operation ID*: `get_utility_llm_config_api_v1_config_service_llm_get`

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |

---

### `POST` `/api/v1/config/service-llm`

**Set Utility Llm**

Set or clear the utility LLM profile.

*Operation ID*: `set_utility_llm_api_v1_config_service_llm_post`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/config/settings`

**Get Settings**

Get all application settings.

*Operation ID*: `get_settings_api_v1_config_settings_get`

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |

---

### `PUT` `/api/v1/config/settings`

**Update Settings**

Update application settings.

*Operation ID*: `update_settings_api_v1_config_settings_put`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/config/settings/project/{project_id}`

**Get Project Settings**

Get settings for a specific project (merged with global defaults).

*Operation ID*: `get_project_settings_api_v1_config_settings_project__project_id__get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `project_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/config/validate-service-llm`

**Validate Utility Llm**

Validate whether a given profile is suitable as utility LLM.

*Operation ID*: `validate_utility_llm_api_v1_config_validate_service_llm_post`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/config/version`

**Get Version**

Return the current application version from the single source of truth.

*Operation ID*: `get_version_api_v1_config_version_get`

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |

---

## debate

### `GET` `/api/v1/debate`

**List Debates**

List all debates (newest first) — for history panel.

Query params:
    status: Filter by debate status (pending, running, completed, failed).
    search: Full-text search in case_preview (case-insensitive).

*Operation ID*: `list_debates_api_v1_debate_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `limit` | query | integer |  |  |
| `offset` | query | integer |  |  |
| `status` | query | string |  |  |
| `search` | query | string |  |  |
| `X-Project-Id` | header | string | ✓ | Active project UUID |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/debate`

**Create Debate**

Create a new debate (status = pending).

*Operation ID*: `create_debate_api_v1_debate_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `X-Project-Id` | header | string | ✓ | Active project UUID |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `201` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/debate/cross-project/running`

**Find Running Debate Across Projects**

Find the first running debate across ALL projects.

Used by the Dashboard to detect externally-started debates (e.g. via A2A)
that may live in a different project than the active one.

*Operation ID*: `find_running_debate_across_projects_api_v1_debate_cross_project_running_get`

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |

---

### `POST` `/api/v1/debate/from-layout/{layout_id}`

**Start Debate From Layout**

Start a debate directly from a canvas layout.

Converts the layout to a WorkflowDefinition, creates a debate with
bundle-resolved agent profiles, and launches the workflow.

*Operation ID*: `start_debate_from_layout_api_v1_debate_from_layout__layout_id__post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `layout_id` | path | string | ✓ |  |
| `X-Project-Id` | header | string | ✓ | Active project UUID |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `201` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/debate/from-workflow/{workflow_id}`

**Start Debate From Workflow**

Start a debate from an existing WorkflowDefinition.

The workflow's wf-agent nodes (with bundle_id references) are resolved
during execution via the WorkflowCompiler.

*Operation ID*: `start_debate_from_workflow_api_v1_debate_from_workflow__workflow_id__post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `workflow_id` | path | string | ✓ |  |
| `X-Project-Id` | header | string | ✓ | Active project UUID |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `201` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/debate/on-completed`

**On Debate Completed Hook**

Internal hook triggered after a debate transitions to completed status (P3).

Creates a DMS document with the debate transcript for future RAG retrieval.

*Operation ID*: `on_debate_completed_hook_api_v1_debate_on_completed_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `debate_id` | query | string | ✓ |  |
| `X-Project-Id` | header | string | ✓ | Active project UUID |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `DELETE` `/api/v1/debate/{debate_id}`

**Delete Debate**

Delete a debate and its associated audit events.

*Operation ID*: `delete_debate_api_v1_debate__debate_id__delete`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `debate_id` | path | string | ✓ |  |
| `X-Project-Id` | header | string | ✓ | Active project UUID |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/debate/{debate_id}`

**Get Debate**

Get debate status and progress.

*Operation ID*: `get_debate_api_v1_debate__debate_id__get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `debate_id` | path | string | ✓ |  |
| `X-Project-Id` | header | string | ✓ | Active project UUID |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/debate/{debate_id}/cancel`

**Cancel Debate**

Cancel a running debate.

Sets a cancellation flag that the workflow checks between rounds.
Idempotent: if the debate already completed or failed, returns the
current status instead of raising an error.

*Operation ID*: `cancel_debate_api_v1_debate__debate_id__cancel_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `debate_id` | path | string | ✓ |  |
| `X-Project-Id` | header | string | ✓ | Active project UUID |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/debate/{debate_id}/continue`

**Continue Debate**

Start a new debate continuing from a completed one (P0).

The previous debate's results are used as context for the new case text.

*Operation ID*: `continue_debate_api_v1_debate__debate_id__continue_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `debate_id` | path | string | ✓ |  |
| `X-Project-Id` | header | string | ✓ | Active project UUID |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `PUT` `/api/v1/debate/{debate_id}/documents`

**Assign Documents**

Assign or update documents for a pending debate.

Can be called before or after debate creation, but only while the
debate is still pending (not yet started).

*Operation ID*: `assign_documents_api_v1_debate__debate_id__documents_put`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `debate_id` | path | string | ✓ |  |
| `X-Project-Id` | header | string | ✓ | Active project UUID |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/debate/{debate_id}/fork`

**Fork Debate**

Fork an existing debate with optional modifications (P4).

Creates a deep copy with configurable fork point and persona/prompt changes.

*Operation ID*: `fork_debate_api_v1_debate__debate_id__fork_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `debate_id` | path | string | ✓ |  |
| `X-Project-Id` | header | string | ✓ | Active project UUID |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/debate/{debate_id}/fork-from-consensus`

**Fork From Consensus**

Create a new debate from the consensus of a completed one (P2).

The consensus summary is used as the starting context.

*Operation ID*: `fork_from_consensus_api_v1_debate__debate_id__fork_from_consensus_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `debate_id` | path | string | ✓ |  |
| `X-Project-Id` | header | string | ✓ | Active project UUID |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/debate/{debate_id}/forks`

**List Forks**

List all forks originating from a given debate (P4).

Allows tracing the fork tree of a debate.

*Operation ID*: `list_forks_api_v1_debate__debate_id__forks_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `debate_id` | path | string | ✓ |  |
| `limit` | query | integer |  |  |
| `offset` | query | integer |  |  |
| `X-Project-Id` | header | string | ✓ | Active project UUID |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/debate/{debate_id}/oob`

**Submit Oob Input**

Submit an out-of-band input for a running debate.

The input is queued and will be consumed by the next agent that matches
the routing target.  Emits an SSE event for visualization.

*Operation ID*: `submit_oob_input_api_v1_debate__debate_id__oob_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `debate_id` | path | string | ✓ |  |
| `X-Project-Id` | header | string | ✓ | Active project UUID |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/debate/{debate_id}/start`

**Start Debate**

Start a pending debate — launches the workflow in a background task.

Returns immediately with status=running.  Real-time progress is
delivered via the SSE stream endpoint.

*Operation ID*: `start_debate_api_v1_debate__debate_id__start_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `debate_id` | path | string | ✓ |  |
| `X-Project-Id` | header | string | ✓ | Active project UUID |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/debate/{debate_id}/stream`

**Stream Debate**

SSE endpoint for real-time debate updates.

Accepts ``project_id`` as a **query parameter** because the browser's
``EventSource`` API cannot send custom HTTP headers.

*Operation ID*: `stream_debate_api_v1_debate__debate_id__stream_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `debate_id` | path | string | ✓ |  |
| `project_id` | query | string | ✓ | Project UUID (query param, since EventSource cannot send headers) |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

## dms

### `GET` `/api/v1/dms/documents`

**List Documents**

List documents in the active project.

*Operation ID*: `list_documents_api_v1_dms_documents_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `X-Project-Id` | header | string | ✓ | Active project UUID |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/dms/documents`

**Upload Document**

Upload a document to the active project.

*Operation ID*: `upload_document_api_v1_dms_documents_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `X-Project-Id` | header | string | ✓ | Active project UUID |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `DELETE` `/api/v1/dms/documents/{document_id}`

**Delete Document**

Delete a document from the active project.

*Operation ID*: `delete_document_api_v1_dms_documents__document_id__delete`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `document_id` | path | string | ✓ |  |
| `X-Project-Id` | header | string | ✓ | Active project UUID |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/dms/documents/{document_id}`

**Get Document**

Get a single document with its content for viewing.

*Operation ID*: `get_document_api_v1_dms_documents__document_id__get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `document_id` | path | string | ✓ |  |
| `X-Project-Id` | header | string | ✓ | Active project UUID |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `DELETE` `/api/v1/dms/documents/{document_id}/rag`

**Remove From Rag**

Remove a document from manual RAG context.

*Operation ID*: `remove_from_rag_api_v1_dms_documents__document_id__rag_delete`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `document_id` | path | string | ✓ |  |
| `X-Project-Id` | header | string | ✓ | Active project UUID |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/dms/documents/{document_id}/rag`

**Add To Rag**

Add a document to manual RAG context.

*Operation ID*: `add_to_rag_api_v1_dms_documents__document_id__rag_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `document_id` | path | string | ✓ |  |
| `X-Project-Id` | header | string | ✓ | Active project UUID |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/dms/ocr-status`

**Ocr Status**

Check which OCR engines are available for image text extraction.

Returns:
    Dict with ``available`` (bool) and ``engine`` (str or null)
    indicating the available OCR engine ("paddleocr" or "tesseract").

*Operation ID*: `ocr_status_api_v1_dms_ocr_status_get`

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |

---

### `GET` `/api/v1/dms/rag/manual`

**List Manual Rag**

List document IDs in manual RAG context.

*Operation ID*: `list_manual_rag_api_v1_dms_rag_manual_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `X-Project-Id` | header | string | ✓ | Active project UUID |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/dms/rag/search`

**Search Rag**

Search RAG context for relevant chunks.

*Operation ID*: `search_rag_api_v1_dms_rag_search_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `query` | query | string | ✓ |  |
| `k` | query | integer |  |  |
| `X-Project-Id` | header | string | ✓ | Active project UUID |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

## health

### `GET` `/health`

**Health**

Return application health status.

*Operation ID*: `health_health_get`

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |

---

## hitl

### `POST` `/api/v1/debate/{debate_id}/extension-decision`

**Extension Decision**

Respond to an extension request — grant or deny extra rounds.

Called by the moderator (or user) to decide whether additional rounds
should be debated.

*Operation ID*: `extension_decision_api_v1_debate__debate_id__extension_decision_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `debate_id` | path | string | ✓ |  |
| `X-Project-Id` | header | string | ✓ | Active project UUID |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/debate/{debate_id}/extension-request`

**Request Extension**

Submit an extension request for additional debate rounds.

Called by the workflow when consensus is not reached and extra rounds
are enabled. Creates an interrupt that the moderator can respond to.

*Operation ID*: `request_extension_api_v1_debate__debate_id__extension_request_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `debate_id` | path | string | ✓ |  |
| `X-Project-Id` | header | string | ✓ | Active project UUID |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/debate/{debate_id}/hitl/status`

**Get Hitl Status**

Get the current HITL status for a debate.

*Operation ID*: `get_hitl_status_api_v1_debate__debate_id__hitl_status_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `debate_id` | path | string | ✓ |  |
| `X-Project-Id` | header | string | ✓ | Active project UUID |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/debate/{debate_id}/inject`

**Inject Context**

Inject user context into a running debate.

The injected content will be available to agents in subsequent turns.
Non-blocking — the debate continues while the injection is queued.

*Operation ID*: `inject_context_api_v1_debate__debate_id__inject_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `debate_id` | path | string | ✓ |  |
| `X-Project-Id` | header | string | ✓ | Active project UUID |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `201` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/debate/{debate_id}/interactions`

**List Interactions**

Get interaction history for a debate (paginated).

*Operation ID*: `list_interactions_api_v1_debate__debate_id__interactions_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `debate_id` | path | string | ✓ |  |
| `offset` | query | integer |  |  |
| `limit` | query | integer |  |  |
| `interaction_type` | query | string |  |  |
| `X-Project-Id` | header | string | ✓ | Active project UUID |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/debate/{debate_id}/pause`

**Pause Debate**

Pause or resume a running debate.

When paused, the workflow will check the pause state at each node
boundary and wait until resumed.

*Operation ID*: `pause_debate_api_v1_debate__debate_id__pause_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `debate_id` | path | string | ✓ |  |
| `X-Project-Id` | header | string | ✓ | Active project UUID |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/debate/{debate_id}/respond`

**Respond To Query**

Respond to an agent's clarification query.

Resolves the active interrupt and allows the debate workflow to resume.

*Operation ID*: `respond_to_query_api_v1_debate__debate_id__respond_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `debate_id` | path | string | ✓ |  |
| `X-Project-Id` | header | string | ✓ | Active project UUID |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

## i18n

### `GET` `/api/v1/i18n/bulk-translate`

**List Translation Jobs**

List all translation jobs.

*Operation ID*: `list_translation_jobs_api_v1_i18n_bulk_translate_get`

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |

---

### `GET` `/api/v1/i18n/bulk-translate`

**List Translation Jobs**

List all translation jobs.

*Operation ID*: `list_translation_jobs_api_v1_i18n_bulk_translate_get`

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |

---

### `POST` `/api/v1/i18n/bulk-translate`

**Bulk Translate**

Start an async bulk translation job. Returns job_id for polling.

*Operation ID*: `bulk_translate_api_v1_i18n_bulk_translate_post`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/i18n/bulk-translate`

**Bulk Translate**

Start an async bulk translation job. Returns job_id for polling.

*Operation ID*: `bulk_translate_api_v1_i18n_bulk_translate_post`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/i18n/bulk-translate/{job_id}/status`

**Get Translation Job Status**

Get the status and progress of a translation job.

*Operation ID*: `get_translation_job_status_api_v1_i18n_bulk_translate__job_id__status_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `job_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/i18n/bulk-translate/{job_id}/status`

**Get Translation Job Status**

Get the status and progress of a translation job.

*Operation ID*: `get_translation_job_status_api_v1_i18n_bulk_translate__job_id__status_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `job_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/i18n/coverage`

**Get Coverage**

Coverage-Report für alle Sprachen.

*Operation ID*: `get_coverage_api_v1_i18n_coverage_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `namespace` | query | string |  |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/i18n/coverage`

**Get Coverage**

Coverage-Report für alle Sprachen.

*Operation ID*: `get_coverage_api_v1_i18n_coverage_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `namespace` | query | string |  |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/i18n/custom-locales`

**List Custom Locales**

List all custom-registered locales.

*Operation ID*: `list_custom_locales_api_v1_i18n_custom_locales_get`

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |

---

### `GET` `/api/v1/i18n/custom-locales`

**List Custom Locales**

List all custom-registered locales.

*Operation ID*: `list_custom_locales_api_v1_i18n_custom_locales_get`

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |

---

### `GET` `/api/v1/i18n/locales`

**Get Supported Locales**

Liste der unterstützten Sprachen mit Metadaten.

*Operation ID*: `get_supported_locales_api_v1_i18n_locales_get`

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |

---

### `GET` `/api/v1/i18n/locales`

**Get Supported Locales**

Liste der unterstützten Sprachen mit Metadaten.

*Operation ID*: `get_supported_locales_api_v1_i18n_locales_get`

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |

---

### `POST` `/api/v1/i18n/locales`

**Register Locale**

Register a new custom locale not in the default set.

*Operation ID*: `register_locale_api_v1_i18n_locales_post`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `201` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/i18n/locales`

**Register Locale**

Register a new custom locale not in the default set.

*Operation ID*: `register_locale_api_v1_i18n_locales_post`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `201` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/i18n/stats`

**Get Stats**

Übersetzungsstatistiken pro Sprache.

*Operation ID*: `get_stats_api_v1_i18n_stats_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `namespace` | query | string |  |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/i18n/stats`

**Get Stats**

Übersetzungsstatistiken pro Sprache.

*Operation ID*: `get_stats_api_v1_i18n_stats_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `namespace` | query | string |  |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/i18n/strings/{locale}`

**Get Locale Strings**

Per-locale string details with translation status, source, dates.

*Operation ID*: `get_locale_strings_api_v1_i18n_strings__locale__get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `locale` | path | string | ✓ |  |
| `namespace` | query | string |  |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/i18n/strings/{locale}`

**Get Locale Strings**

Per-locale string details with translation status, source, dates.

*Operation ID*: `get_locale_strings_api_v1_i18n_strings__locale__get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `locale` | path | string | ✓ |  |
| `namespace` | query | string |  |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/i18n/{locale}`

**Get Translations**

Übersetzungen für eine Sprache abrufen.

When merge_langpacks is True (default), strings from language-pack
namespaces (langpack:*) are merged on top of the global namespace.

*Operation ID*: `get_translations_api_v1_i18n__locale__get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `locale` | path | string | ✓ |  |
| `namespace` | query | string |  |  |
| `keys` | query | string |  | Komma-separierte Liste von Keys |
| `merge_langpacks` | query | boolean |  | Merge language-pack namespaces |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/i18n/{locale}`

**Get Translations**

Übersetzungen für eine Sprache abrufen.

When merge_langpacks is True (default), strings from language-pack
namespaces (langpack:*) are merged on top of the global namespace.

*Operation ID*: `get_translations_api_v1_i18n__locale__get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `locale` | path | string | ✓ |  |
| `namespace` | query | string |  |  |
| `keys` | query | string |  | Komma-separierte Liste von Keys |
| `merge_langpacks` | query | boolean |  | Merge language-pack namespaces |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/i18n/{locale}`

**Set Translations**

Mehrere Übersetzungen für eine Sprache setzen.

*Operation ID*: `set_translations_api_v1_i18n__locale__post`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/i18n/{locale}`

**Set Translations**

Mehrere Übersetzungen für eine Sprache setzen.

*Operation ID*: `set_translations_api_v1_i18n__locale__post`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/i18n/{locale}/export-as-pack`

**Export Language Pack**

Export all UI translations for a locale as a Language Pack ZIP.

Creates a ZIP archive containing:
- manifest.json (ModuleManifest with type=language-pack)
- ui_strings.json (key-value pairs for the locale)

*Operation ID*: `export_language_pack_api_v1_i18n__locale__export_as_pack_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `locale` | path | string | ✓ |  |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/i18n/{locale}/export-as-pack`

**Export Language Pack**

Export all UI translations for a locale as a Language Pack ZIP.

Creates a ZIP archive containing:
- manifest.json (ModuleManifest with type=language-pack)
- ui_strings.json (key-value pairs for the locale)

*Operation ID*: `export_language_pack_api_v1_i18n__locale__export_as_pack_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `locale` | path | string | ✓ |  |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `DELETE` `/api/v1/i18n/{locale}/{key}`

**Delete Translation**

Übersetzung löschen.

*Operation ID*: `delete_translation_api_v1_i18n__locale___key__delete`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `locale` | path | string | ✓ |  |
| `key` | path | string | ✓ |  |
| `namespace` | query | string |  |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `DELETE` `/api/v1/i18n/{locale}/{key}`

**Delete Translation**

Übersetzung löschen.

*Operation ID*: `delete_translation_api_v1_i18n__locale___key__delete`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `locale` | path | string | ✓ |  |
| `key` | path | string | ✓ |  |
| `namespace` | query | string |  |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/i18n/{locale}/{key}`

**Get Single Translation**

Einzelne Übersetzung abrufen.

*Operation ID*: `get_single_translation_api_v1_i18n__locale___key__get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `locale` | path | string | ✓ |  |
| `key` | path | string | ✓ |  |
| `namespace` | query | string |  |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/i18n/{locale}/{key}`

**Get Single Translation**

Einzelne Übersetzung abrufen.

*Operation ID*: `get_single_translation_api_v1_i18n__locale___key__get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `locale` | path | string | ✓ |  |
| `key` | path | string | ✓ |  |
| `namespace` | query | string |  |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `PUT` `/api/v1/i18n/{locale}/{key}`

**Update Translation**

Einzelne Übersetzung erstellen/aktualisieren.

*Operation ID*: `update_translation_api_v1_i18n__locale___key__put`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `locale` | path | string | ✓ |  |
| `key` | path | string | ✓ |  |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `PUT` `/api/v1/i18n/{locale}/{key}`

**Update Translation**

Einzelne Übersetzung erstellen/aktualisieren.

*Operation ID*: `update_translation_api_v1_i18n__locale___key__put`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `locale` | path | string | ✓ |  |
| `key` | path | string | ✓ |  |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

## input-composer

### `GET` `/api/v1/input-plugins`

**List Input Plugins**

List all registered input plugins with their config schemas and UI hints.

*Operation ID*: `list_input_plugins_api_v1_input_plugins_get`

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |

---

### `GET` `/api/v1/input-plugins`

**List Input Plugins**

List all registered input plugins with their config schemas and UI hints.

*Operation ID*: `list_input_plugins_api_v1_input_plugins_get`

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |

---

### `POST` `/api/v1/input/a2a/{task_id}/approve`

**Approve A2A**

Approve a pending A2A inbound request.

*Operation ID*: `approve_a2a_api_v1_input_a2a__task_id__approve_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `task_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/input/a2a/{task_id}/approve`

**Approve A2A**

Approve a pending A2A inbound request.

*Operation ID*: `approve_a2a_api_v1_input_a2a__task_id__approve_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `task_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/input/a2a/{task_id}/reject`

**Reject A2A**

Reject a pending A2A inbound request.

*Operation ID*: `reject_a2a_api_v1_input_a2a__task_id__reject_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `task_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/input/a2a/{task_id}/reject`

**Reject A2A**

Reject a pending A2A inbound request.

*Operation ID*: `reject_a2a_api_v1_input_a2a__task_id__reject_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `task_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/input/jobs`

**List Input Jobs**

List input jobs with optional filters.

Query parameters:
- ``status``: Filter by job status (queued, processing, completed, failed, pending_approval)
- ``plugin_key``: Filter by plugin key (e.g. standard_text, a2a_inbound)
- ``limit``: Max results (default 50)
- ``offset``: Pagination offset (default 0)

*Operation ID*: `list_input_jobs_api_v1_input_jobs_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `status` | query | string |  |  |
| `plugin_key` | query | string |  |  |
| `limit` | query | integer |  |  |
| `offset` | query | integer |  |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/input/jobs`

**List Input Jobs**

List input jobs with optional filters.

Query parameters:
- ``status``: Filter by job status (queued, processing, completed, failed, pending_approval)
- ``plugin_key``: Filter by plugin key (e.g. standard_text, a2a_inbound)
- ``limit``: Max results (default 50)
- ``offset``: Pagination offset (default 0)

*Operation ID*: `list_input_jobs_api_v1_input_jobs_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `status` | query | string |  |  |
| `plugin_key` | query | string |  |  |
| `limit` | query | integer |  |  |
| `offset` | query | integer |  |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `DELETE` `/api/v1/input/jobs/{job_id}`

**Delete Input Job**

Delete an input job.

*Operation ID*: `delete_input_job_api_v1_input_jobs__job_id__delete`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `job_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `204` | Successful Response |
| `422` | Validation Error |

---

### `DELETE` `/api/v1/input/jobs/{job_id}`

**Delete Input Job**

Delete an input job.

*Operation ID*: `delete_input_job_api_v1_input_jobs__job_id__delete`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `job_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `204` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/input/jobs/{job_id}`

**Get Input Job Status**

Get the status and metadata of an input job.

*Operation ID*: `get_input_job_status_api_v1_input_jobs__job_id__get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `job_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/input/jobs/{job_id}`

**Get Input Job Status**

Get the status and metadata of an input job.

*Operation ID*: `get_input_job_status_api_v1_input_jobs__job_id__get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `job_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/input/launch`

**Launch Workflow From Input**

Launch a workflow execution from a completed input job.

Takes a completed InputJob (with its DebateInput artifact), resolves
a workflow definition, and starts execution via the workflow runner.

This bridges the Input Composer pipeline to the Workflow Execution
pipeline — the missing link between input capture and debate execution.

*Operation ID*: `launch_workflow_from_input_api_v1_input_launch_post`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/input/launch`

**Launch Workflow From Input**

Launch a workflow execution from a completed input job.

Takes a completed InputJob (with its DebateInput artifact), resolves
a workflow definition, and starts execution via the workflow runner.

This bridges the Input Composer pipeline to the Workflow Execution
pipeline — the missing link between input capture and debate execution.

*Operation ID*: `launch_workflow_from_input_api_v1_input_launch_post`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/input/stt/stream`

**Stt Stream**

STT audio streaming endpoint.

Receives audio blobs via POST body and returns Server-Sent Events (SSE)
with ``event: partial`` for intermediate results and ``event: final``
for the completed transcript.

The request body should be raw audio bytes (WebM/Opus or WAV).
Query parameters:
- ``profile_id``: LLM profile ID with protocol='stt' (optional, uses default)
- ``language``: Language code (default: 'de')

*Operation ID*: `stt_stream_api_v1_input_stt_stream_post`

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |

---

### `POST` `/api/v1/input/stt/stream`

**Stt Stream**

STT audio streaming endpoint.

Receives audio blobs via POST body and returns Server-Sent Events (SSE)
with ``event: partial`` for intermediate results and ``event: final``
for the completed transcript.

The request body should be raw audio bytes (WebM/Opus or WAV).
Query parameters:
- ``profile_id``: LLM profile ID with protocol='stt' (optional, uses default)
- ``language``: Language code (default: 'de')

*Operation ID*: `stt_stream_api_v1_input_stt_stream_post`

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |

---

### `POST` `/api/v1/input/submit`

**Submit Input**

Submit input for processing by an Input Plugin.

*Operation ID*: `submit_input_api_v1_input_submit_post`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `202` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/input/submit`

**Submit Input**

Submit input for processing by an Input Plugin.

*Operation ID*: `submit_input_api_v1_input_submit_post`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `202` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/mcp/tools/call`

**Mcp Tools Call**

Reserved endpoint for future MCP server integration.

Currently returns 501 Not Implemented.

*Operation ID*: `mcp_tools_call_api_v1_mcp_tools_call_post`

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |

---

### `POST` `/api/v1/mcp/tools/call`

**Mcp Tools Call**

Reserved endpoint for future MCP server integration.

Currently returns 501 Not Implemented.

*Operation ID*: `mcp_tools_call_api_v1_mcp_tools_call_post`

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |

---

## modules

### `GET` `/api/v1/modules/`

**List Modules**

List all installed modules with DB status.

*Operation ID*: `list_modules_api_v1_modules__get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `category` | query | string |  | Filter by category |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/modules/available`

**List Available Modules**

List modules available for installation from the official registry.

Currently returns an empty list — all modules are discovered from the
local `modules/` directory. A remote registry may be added later.

*Operation ID*: `list_available_modules_api_v1_modules_available_get`

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |

---

### `POST` `/api/v1/modules/install`

**Install Module**

Install a module from local files or a URL.

*Operation ID*: `install_module_api_v1_modules_install_post`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `201` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/modules/validate`

**Validate Module**

Validate a module manifest without installing it.

*Operation ID*: `validate_module_api_v1_modules_validate_post`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/modules/{module_id}`

**Get Module**

Get detailed info about a specific module.

*Operation ID*: `get_module_api_v1_modules__module_id__get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `module_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/modules/{module_id}/disable`

**Disable Module**

Disable (deactivate) a module.

*Operation ID*: `disable_module_api_v1_modules__module_id__disable_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `module_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/modules/{module_id}/duplicate`

**Duplicate Module**

Duplicate a module with a new ID.

*Operation ID*: `duplicate_module_api_v1_modules__module_id__duplicate_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `module_id` | path | string | ✓ |  |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `201` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/modules/{module_id}/enable`

**Enable Module**

Enable (activate) a module.

*Operation ID*: `enable_module_api_v1_modules__module_id__enable_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `module_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/modules/{module_id}/export`

**Export Module**

Export a module as a ZIP archive for sharing/uploading to GitHub.

*Operation ID*: `export_module_api_v1_modules__module_id__export_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `module_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/modules/{module_id}/profile`

**Get Module Profile**

Get the parsed profile data for a module.

*Operation ID*: `get_module_profile_api_v1_modules__module_id__profile_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `module_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `PUT` `/api/v1/modules/{module_id}/profile`

**Update Module Profile**

Update a module's profile data.

*Operation ID*: `update_module_profile_api_v1_modules__module_id__profile_put`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `module_id` | path | string | ✓ |  |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/modules/{module_id}/translate`

**Translate Module**

Initiate translation of a module to the target language.

*Operation ID*: `translate_module_api_v1_modules__module_id__translate_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `module_id` | path | string | ✓ |  |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/modules/{module_id}/translations`

**Get Translation Status**

Get the translation status for all files in a module.

*Operation ID*: `get_translation_status_api_v1_modules__module_id__translations_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `module_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/modules/{module_id}/uninstall`

**Uninstall Module**

Uninstall a module.

*Operation ID*: `uninstall_module_api_v1_modules__module_id__uninstall_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `module_id` | path | string | ✓ |  |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `PUT` `/api/v1/modules/{module_id}/update`

**Update Module**

Update a module to the latest available version.

*Operation ID*: `update_module_api_v1_modules__module_id__update_put`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `module_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

## optimization-proposals

### `GET` `/api/v1/optimization-proposals`

**List Proposals**

List optimization proposals, optionally filtered.

*Operation ID*: `list_proposals_api_v1_optimization_proposals_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `status` | query | string |  |  |
| `workflow_id` | query | string |  |  |
| `limit` | query | integer |  |  |
| `offset` | query | integer |  |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/optimization-proposals`

**List Proposals**

List optimization proposals, optionally filtered.

*Operation ID*: `list_proposals_api_v1_optimization_proposals_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `status` | query | string |  |  |
| `workflow_id` | query | string |  |  |
| `limit` | query | integer |  |  |
| `offset` | query | integer |  |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/optimization-proposals/{proposal_id}`

**Get Proposal**

Get a single optimization proposal.

*Operation ID*: `get_proposal_api_v1_optimization_proposals__proposal_id__get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `proposal_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/optimization-proposals/{proposal_id}`

**Get Proposal**

Get a single optimization proposal.

*Operation ID*: `get_proposal_api_v1_optimization_proposals__proposal_id__get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `proposal_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/optimization-proposals/{proposal_id}/approve`

**Approve Proposal**

Approve a proposal — creates a new WorkflowDefinition version.

*Operation ID*: `approve_proposal_api_v1_optimization_proposals__proposal_id__approve_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `proposal_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/optimization-proposals/{proposal_id}/approve`

**Approve Proposal**

Approve a proposal — creates a new WorkflowDefinition version.

*Operation ID*: `approve_proposal_api_v1_optimization_proposals__proposal_id__approve_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `proposal_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/optimization-proposals/{proposal_id}/reject`

**Reject Proposal**

Reject a proposal.

*Operation ID*: `reject_proposal_api_v1_optimization_proposals__proposal_id__reject_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `proposal_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/optimization-proposals/{proposal_id}/reject`

**Reject Proposal**

Reject a proposal.

*Operation ID*: `reject_proposal_api_v1_optimization_proposals__proposal_id__reject_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `proposal_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/workflows/{workflow_id}/reflect`

**Reflect On Workflow**

Generate an optimization proposal for a workflow.

*Operation ID*: `reflect_on_workflow_api_v1_workflows__workflow_id__reflect_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `workflow_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `201` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/workflows/{workflow_id}/reflect`

**Reflect On Workflow**

Generate an optimization proposal for a workflow.

*Operation ID*: `reflect_on_workflow_api_v1_workflows__workflow_id__reflect_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `workflow_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `201` | Successful Response |
| `422` | Validation Error |

---

## output-composer

### `GET` `/api/v1/output-plugins`

**List Output Plugins**

List all registered output plugins with their config schemas.

*Operation ID*: `list_output_plugins_api_v1_output_plugins_get`

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |

---

### `GET` `/api/v1/output-plugins`

**List Output Plugins**

List all registered output plugins with their config schemas.

*Operation ID*: `list_output_plugins_api_v1_output_plugins_get`

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |

---

### `DELETE` `/api/v1/render-jobs/{job_id}`

**Delete Render Job**

Delete a render job and its output files.

Performs a hard delete — removes the job record and optionally
the output directory.

*Operation ID*: `delete_render_job_api_v1_render_jobs__job_id__delete`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `job_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `204` | Successful Response |
| `422` | Validation Error |

---

### `DELETE` `/api/v1/render-jobs/{job_id}`

**Delete Render Job**

Delete a render job and its output files.

Performs a hard delete — removes the job record and optionally
the output directory.

*Operation ID*: `delete_render_job_api_v1_render_jobs__job_id__delete`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `job_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `204` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/render-jobs/{job_id}`

**Get Render Job Status**

Get the status and metadata of a render job.

*Operation ID*: `get_render_job_status_api_v1_render_jobs__job_id__get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `job_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/render-jobs/{job_id}`

**Get Render Job Status**

Get the status and metadata of a render job.

*Operation ID*: `get_render_job_status_api_v1_render_jobs__job_id__get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `job_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/render-jobs/{job_id}/download`

**Download Render File**

Download a generated output file.

Args:
    job_id: The render job ID.
    file_index: Index of the file in output_files (default 0).

*Operation ID*: `download_render_file_api_v1_render_jobs__job_id__download_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `job_id` | path | string | ✓ |  |
| `file_index` | query | integer |  |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/render-jobs/{job_id}/download`

**Download Render File**

Download a generated output file.

Args:
    job_id: The render job ID.
    file_index: Index of the file in output_files (default 0).

*Operation ID*: `download_render_file_api_v1_render_jobs__job_id__download_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `job_id` | path | string | ✓ |  |
| `file_index` | query | integer |  |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/render-sessions`

**Search Sessions**

Search completed sessions by ID or debate title for autocomplete.

Returns sessions that have a saved DebateArtifact.

*Operation ID*: `search_sessions_api_v1_render_sessions_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `q` | query | string |  |  |
| `limit` | query | integer |  |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/render-sessions`

**Search Sessions**

Search completed sessions by ID or debate title for autocomplete.

Returns sessions that have a saved DebateArtifact.

*Operation ID*: `search_sessions_api_v1_render_sessions_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `q` | query | string |  |  |
| `limit` | query | integer |  |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/sessions/{session_id}/render`

**Create Render Job**

Start a render job for a completed session.

The job runs asynchronously.  Poll GET /api/v1/render-jobs/{job_id}
for status updates.

*Operation ID*: `create_render_job_api_v1_sessions__session_id__render_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `session_id` | path | string | ✓ |  |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `202` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/sessions/{session_id}/render`

**Create Render Job**

Start a render job for a completed session.

The job runs asynchronously.  Poll GET /api/v1/render-jobs/{job_id}
for status updates.

*Operation ID*: `create_render_job_api_v1_sessions__session_id__render_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `session_id` | path | string | ✓ |  |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `202` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/tts-voices`

**List Tts Voices**

List available TTS voices with optional filters.

Args:
    language: Filter by language prefix (e.g. "de", "en").
    gender: Filter by gender ("Male" / "Female").
    engine: If "mimo_tts", return MiMo voices instead of edge-tts voices.

*Operation ID*: `list_tts_voices_api_v1_tts_voices_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `language` | query | string |  |  |
| `gender` | query | string |  |  |
| `engine` | query | string |  |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/tts-voices`

**List Tts Voices**

List available TTS voices with optional filters.

Args:
    language: Filter by language prefix (e.g. "de", "en").
    gender: Filter by gender ("Male" / "Female").
    engine: If "mimo_tts", return MiMo voices instead of edge-tts voices.

*Operation ID*: `list_tts_voices_api_v1_tts_voices_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `language` | query | string |  |  |
| `gender` | query | string |  |  |
| `engine` | query | string |  |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

## profiles

### `GET` `/api/v1/profiles/agents`

**List Agent Personas**

List all agent personas, optionally filtered by role.

*Operation ID*: `list_agent_personas_api_v1_profiles_agents_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `role` | query | string |  | Filter by role |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/profiles/agents`

**Create Agent Persona**

Create a new agent persona.

*Operation ID*: `create_agent_persona_api_v1_profiles_agents_post`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `201` | Successful Response |
| `422` | Validation Error |

---

### `DELETE` `/api/v1/profiles/agents/{persona_id}`

**Delete Agent Persona**

Delete an agent persona.

*Operation ID*: `delete_agent_persona_api_v1_profiles_agents__persona_id__delete`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `persona_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/profiles/agents/{persona_id}`

**Get Agent Persona**

Get a specific agent persona by ID.

*Operation ID*: `get_agent_persona_api_v1_profiles_agents__persona_id__get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `persona_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `PUT` `/api/v1/profiles/agents/{persona_id}`

**Update Agent Persona**

Update an existing agent persona.

*Operation ID*: `update_agent_persona_api_v1_profiles_agents__persona_id__put`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `persona_id` | path | string | ✓ |  |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/profiles/cost-estimate`

**Estimate Cost**

Estimate the cost of a debate run.

*Operation ID*: `estimate_cost_api_v1_profiles_cost_estimate_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `llm_profile_id` | query | string | ✓ | LLM profile ID |
| `num_agents` | query | integer |  | Number of agents |
| `num_rounds` | query | integer |  | Number of rounds |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/profiles/llm`

**List Llm Profiles**

List all available LLM profiles.

*Operation ID*: `list_llm_profiles_api_v1_profiles_llm_get`

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |

---

### `POST` `/api/v1/profiles/llm`

**Create Llm Profile**

Create a new LLM profile.

*Operation ID*: `create_llm_profile_api_v1_profiles_llm_post`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `201` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/profiles/llm/service-eligible`

**List Service Eligible Llm Profiles**

List all LLM profiles eligible for utility/background tasks.

*Operation ID*: `list_service_eligible_llm_profiles_api_v1_profiles_llm_service_eligible_get`

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |

---

### `DELETE` `/api/v1/profiles/llm/{profile_id}`

**Delete Llm Profile**

Delete an LLM profile.

*Operation ID*: `delete_llm_profile_api_v1_profiles_llm__profile_id__delete`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `profile_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/profiles/llm/{profile_id}`

**Get Llm Profile**

Get a specific LLM profile by ID.

*Operation ID*: `get_llm_profile_api_v1_profiles_llm__profile_id__get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `profile_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `PUT` `/api/v1/profiles/llm/{profile_id}`

**Update Llm Profile**

Update an existing LLM profile.

*Operation ID*: `update_llm_profile_api_v1_profiles_llm__profile_id__put`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `profile_id` | path | string | ✓ |  |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/profiles/prompts`

**List Prompt Variants**

List all prompt variants.

*Operation ID*: `list_prompt_variants_api_v1_profiles_prompts_get`

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |

---

### `POST` `/api/v1/profiles/prompts`

**Create Prompt Variant**

Create a new prompt variant with per-role prompt content.

*Operation ID*: `create_prompt_variant_api_v1_profiles_prompts_post`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `201` | Successful Response |
| `422` | Validation Error |

---

### `DELETE` `/api/v1/profiles/prompts/{variant_id}`

**Delete Prompt Variant**

Delete a prompt variant.

*Operation ID*: `delete_prompt_variant_api_v1_profiles_prompts__variant_id__delete`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `variant_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/profiles/prompts/{variant_id}/preview`

**Preview Prompt Variant**

Preview a prompt for a specific agent role.

*Operation ID*: `preview_prompt_variant_api_v1_profiles_prompts__variant_id__preview_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `variant_id` | path | string | ✓ |  |
| `agent_role` | query | string | ✓ | Agent role to preview |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/profiles/prompts/{variant_id}/translate`

**Translate Prompt Variant**

Translate a prompt variant to a target language.

*Operation ID*: `translate_prompt_variant_api_v1_profiles_prompts__variant_id__translate_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `variant_id` | path | string | ✓ |  |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

## projects

### `GET` `/api/v1/projects`

**List Projects**

List all projects.

*Operation ID*: `list_projects_api_v1_projects_get`

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |

---

### `POST` `/api/v1/projects`

**Create Project**

Create a new project.

*Operation ID*: `create_project_api_v1_projects_post`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `201` | Successful Response |
| `422` | Validation Error |

---

### `DELETE` `/api/v1/projects/{project_id}`

**Delete Project**

Delete a project. System projects cannot be deleted.

*Operation ID*: `delete_project_api_v1_projects__project_id__delete`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `project_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/projects/{project_id}`

**Get Project**

Get project details.

*Operation ID*: `get_project_api_v1_projects__project_id__get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `project_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `PUT` `/api/v1/projects/{project_id}`

**Update Project**

Update project name/description.

*Operation ID*: `update_project_api_v1_projects__project_id__put`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `project_id` | path | string | ✓ |  |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/projects/{project_id}/config`

**Get Project Config**

Get project-specific configuration.

*Operation ID*: `get_project_config_api_v1_projects__project_id__config_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `project_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `PUT` `/api/v1/projects/{project_id}/config`

**Update Project Config**

Update project-specific configuration.

*Operation ID*: `update_project_config_api_v1_projects__project_id__config_put`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `project_id` | path | string | ✓ |  |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

## reports

### `GET` `/api/v1/reports/{job_id}/download`

**Download Report**

Download a completed report file.

Returns a ``FileResponse`` with the appropriate media type.
Raises 404 if the job is not found or not yet completed.

*Operation ID*: `download_report_api_v1_reports__job_id__download_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `job_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/reports/{job_id}/download`

**Download Report**

Download a completed report file.

Returns a ``FileResponse`` with the appropriate media type.
Raises 404 if the job is not found or not yet completed.

*Operation ID*: `download_report_api_v1_reports__job_id__download_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `job_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/reports/{job_id}/status`

**Get Report Status**

Get the status of a report generation job.

*Operation ID*: `get_report_status_api_v1_reports__job_id__status_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `job_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/reports/{job_id}/status`

**Get Report Status**

Get the status of a report generation job.

*Operation ID*: `get_report_status_api_v1_reports__job_id__status_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `job_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/sessions/{session_id}/report`

**Create Report Job**

Create an async report generation job.

Returns immediately with a ``job_id``.  The report is generated in the
background and can be downloaded via ``GET /api/v1/reports/{job_id}/download``
once the status is ``"completed"``.

*Operation ID*: `create_report_job_api_v1_sessions__session_id__report_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `session_id` | path | string | ✓ |  |
| `X-Project-Id` | header | string | ✓ | Active project UUID |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/sessions/{session_id}/report`

**Create Report Job**

Create an async report generation job.

Returns immediately with a ``job_id``.  The report is generated in the
background and can be downloaded via ``GET /api/v1/reports/{job_id}/download``
once the status is ``"completed"``.

*Operation ID*: `create_report_job_api_v1_sessions__session_id__report_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `session_id` | path | string | ✓ |  |
| `X-Project-Id` | header | string | ✓ | Active project UUID |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/sessions/{session_id}/report/stream`

**Stream Report Progress**

SSE endpoint for real-time report generation progress.

Yields ``report.progress`` events for all report jobs belonging to
the given session.

*Operation ID*: `stream_report_progress_api_v1_sessions__session_id__report_stream_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `session_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/sessions/{session_id}/report/stream`

**Stream Report Progress**

SSE endpoint for real-time report generation progress.

Yields ``report.progress`` events for all report jobs belonging to
the given session.

*Operation ID*: `stream_report_progress_api_v1_sessions__session_id__report_stream_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `session_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

## sessions

### `GET` `/api/v1/sessions`

**List Sessions**

List past debate sessions.

*Operation ID*: `list_sessions_api_v1_sessions_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `limit` | query | integer |  |  |
| `offset` | query | integer |  |  |
| `min_consensus` | query | string |  |  |
| `project_id` | query | string |  |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `DELETE` `/api/v1/sessions/{session_id}`

**Delete Session**

Delete a session.

*Operation ID*: `delete_session_api_v1_sessions__session_id__delete`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `session_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/sessions/{session_id}`

**Get Session**

Get a single session by ID.

*Operation ID*: `get_session_api_v1_sessions__session_id__get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `session_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/sessions/{session_id}/report/{fmt}`

**Download Report**

Generate and download a report (docx or pdf) for a session.

*Operation ID*: `download_report_api_v1_sessions__session_id__report__fmt__get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `session_id` | path | string | ✓ |  |
| `fmt` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/sessions/{session_id}/trace`

**Get Trace**

Get the audit trace for a session.

*Operation ID*: `get_trace_api_v1_sessions__session_id__trace_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `session_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

## system

### `GET` `/api/v1/system/logs`

**Get Logs**

Return recent backend log lines.

Reads the last N lines from the log file, optionally filtered by a search term.

*Operation ID*: `get_logs_api_v1_system_logs_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `lines` | query | integer |  | Number of recent log lines |
| `search` | query | string |  | Filter lines containing this text |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/system/reload-profiles`

**Reload Profiles**

Reload all profiles from YAML files.

Forces ProfileService and PromptService singletons to re-read
their YAML/markdown files from disk. Also clears the workflow
nodes' cached ProfileService instances so running debates pick
up the updated profiles immediately.

*Operation ID*: `reload_profiles_api_v1_system_reload_profiles_post`

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |

---

### `GET` `/health`

**Health**

Return application health status.

*Operation ID*: `health_health_get`

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |

---

## tone-profiles

### `GET` `/api/v1/tone-profiles`

**List Tone Profiles**

List all tone profiles (system + custom + modules), filterable via include_system.

*Operation ID*: `list_tone_profiles_api_v1_tone_profiles_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `include_system` | query | boolean |  |  |
| `limit` | query | integer |  |  |
| `offset` | query | integer |  |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/tone-profiles`

**Create Tone Profile**

Create a new custom tone profile.

``is_system`` is always forced to ``False`` for API-created profiles.

*Operation ID*: `create_tone_profile_api_v1_tone_profiles_post`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `201` | Successful Response |
| `422` | Validation Error |

---

### `DELETE` `/api/v1/tone-profiles/{profile_id}`

**Delete Tone Profile**

Delete a tone profile.

System profiles cannot be deleted (HTTP 403).

*Operation ID*: `delete_tone_profile_api_v1_tone_profiles__profile_id__delete`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `profile_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/tone-profiles/{profile_id}`

**Get Tone Profile**

Get a single tone profile by ID.

*Operation ID*: `get_tone_profile_api_v1_tone_profiles__profile_id__get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `profile_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `PUT` `/api/v1/tone-profiles/{profile_id}`

**Update Tone Profile**

Update an existing tone profile.

System profiles cannot be updated (HTTP 403).

*Operation ID*: `update_tone_profile_api_v1_tone_profiles__profile_id__put`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `profile_id` | path | string | ✓ |  |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

## translation

### `POST` `/api/v1/translation/batch-translate`

**Batch Translate**

Translate multiple modules to the same target language.

Translates each module sequentially. For parallel translation,
use the async endpoint when available.

*Operation ID*: `batch_translate_api_v1_translation_batch_translate_post`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/translation/supported-languages`

**Get Supported Languages**

Get the list of supported target languages for translation.

*Operation ID*: `get_supported_languages_api_v1_translation_supported_languages_get`

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |

---

### `POST` `/api/v1/translation/{module_id}/approve`

**Approve Translation**

Manually approve or reject a specific translation.

Args:
    module_id: The module ID
    file_path: The file path within the module
    approved: True to approve, False to reject

Returns:
    Success status

*Operation ID*: `approve_translation_api_v1_translation__module_id__approve_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `module_id` | path | string | ✓ |  |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/translation/{module_id}/invalidate`

**Invalidate Translation**

Invalidate cached translations to force re-translation.

Args:
    module_id: The module ID
    file_path: If specified, only this file is invalidated
    target_language: If specified, only this language is invalidated

Returns:
    Number of entries invalidated

*Operation ID*: `invalidate_translation_api_v1_translation__module_id__invalidate_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `module_id` | path | string | ✓ |  |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/translation/{module_id}/statistics`

**Get Translation Statistics**

Get translation statistics for a module.

Returns per-language breakdown of total, translated, approved, and average quality.

*Operation ID*: `get_translation_statistics_api_v1_translation__module_id__statistics_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `module_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/translation/{module_id}/status`

**Get Translation Status**

Get the translation status for all files in a module.

Returns per-file details including quality scores and approval status.

*Operation ID*: `get_translation_status_api_v1_translation__module_id__status_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `module_id` | path | string | ✓ |  |
| `target_language` | query | string |  | Filter by target language |
| `approved_only` | query | boolean |  | Show only approved translations |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/translation/{module_id}/translate`

**Translate Module**

Translate a module's content to the target language.

Performs a two-pass translation with optional back-translation QA:
1. Forward translation: EN source → target language
2. (Optional) Back-translation: target → EN for quality verification
3. Semantic comparison to compute quality score
4. Auto-approval if quality meets threshold

Returns detailed status including per-file quality scores.

*Operation ID*: `translate_module_api_v1_translation__module_id__translate_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `module_id` | path | string | ✓ |  |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

## workflow-exec

### `DELETE` `/api/v1/workflow-exec/{session_id}`

**Archive Workflow Session**

Soft-delete a workflow session (sets ``is_archived = 1``).

The session data is preserved but excluded from default listings.
Use ``POST /{session_id}/restore`` to un-archive.

*Operation ID*: `archive_workflow_session_api_v1_workflow_exec__session_id__delete`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `session_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `DELETE` `/api/v1/workflow-exec/{session_id}`

**Archive Workflow Session**

Soft-delete a workflow session (sets ``is_archived = 1``).

The session data is preserved but excluded from default listings.
Use ``POST /{session_id}/restore`` to un-archive.

*Operation ID*: `archive_workflow_session_api_v1_workflow_exec__session_id__delete`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `session_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/workflow-exec/{session_id}/cancel`

**Cancel Workflow**

Cancel a running or paused workflow.

Sets a cancellation flag that the workflow checks between nodes.
Idempotent: if already completed/failed/cancelled, returns current status.

*Operation ID*: `cancel_workflow_api_v1_workflow_exec__session_id__cancel_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `session_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/workflow-exec/{session_id}/cancel`

**Cancel Workflow**

Cancel a running or paused workflow.

Sets a cancellation flag that the workflow checks between nodes.
Idempotent: if already completed/failed/cancelled, returns current status.

*Operation ID*: `cancel_workflow_api_v1_workflow_exec__session_id__cancel_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `session_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/workflow-exec/{session_id}/interject`

**Submit Interjection**

Submit a user interjection for a running workflow session.

The interjection is queued and will be consumed by the next
interjection node in the workflow graph.  Emits an SSE event
for frontend visualization.

*Operation ID*: `submit_interjection_api_v1_workflow_exec__session_id__interject_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `session_id` | path | string | ✓ |  |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/workflow-exec/{session_id}/interject`

**Submit Interjection**

Submit a user interjection for a running workflow session.

The interjection is queued and will be consumed by the next
interjection node in the workflow graph.  Emits an SSE event
for frontend visualization.

*Operation ID*: `submit_interjection_api_v1_workflow_exec__session_id__interject_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `session_id` | path | string | ✓ |  |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/workflow-exec/{session_id}/pause`

**Pause Workflow**

Pause a running workflow.

Sets the pause flag; the workflow will check this between nodes.

*Operation ID*: `pause_workflow_api_v1_workflow_exec__session_id__pause_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `session_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/workflow-exec/{session_id}/pause`

**Pause Workflow**

Pause a running workflow.

Sets the pause flag; the workflow will check this between nodes.

*Operation ID*: `pause_workflow_api_v1_workflow_exec__session_id__pause_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `session_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/workflow-exec/{session_id}/restore`

**Restore Workflow Session**

Restore an archived workflow session (sets ``is_archived = 0``).

*Operation ID*: `restore_workflow_session_api_v1_workflow_exec__session_id__restore_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `session_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/workflow-exec/{session_id}/restore`

**Restore Workflow Session**

Restore an archived workflow session (sets ``is_archived = 0``).

*Operation ID*: `restore_workflow_session_api_v1_workflow_exec__session_id__restore_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `session_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/workflow-exec/{session_id}/resume`

**Resume Workflow**

Resume a paused workflow.

Clears the pause flag and signals the pause event.

*Operation ID*: `resume_workflow_api_v1_workflow_exec__session_id__resume_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `session_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/workflow-exec/{session_id}/resume`

**Resume Workflow**

Resume a paused workflow.

Clears the pause flag and signals the pause event.

*Operation ID*: `resume_workflow_api_v1_workflow_exec__session_id__resume_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `session_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/workflow-exec/{session_id}/state`

**Get Session State**

Get the current execution state for a workflow session.

Returns the latest state snapshot from SQLite.

*Operation ID*: `get_session_state_api_v1_workflow_exec__session_id__state_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `session_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/workflow-exec/{session_id}/state`

**Get Session State**

Get the current execution state for a workflow session.

Returns the latest state snapshot from SQLite.

*Operation ID*: `get_session_state_api_v1_workflow_exec__session_id__state_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `session_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/workflow-exec/{session_id}/stream`

**Stream Workflow Events**

SSE endpoint for real-time workflow execution events.

Subscribes to the event bus and yields events as they are published
by workflow nodes.

*Operation ID*: `stream_workflow_events_api_v1_workflow_exec__session_id__stream_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `session_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/workflow-exec/{session_id}/stream`

**Stream Workflow Events**

SSE endpoint for real-time workflow execution events.

Subscribes to the event bus and yields events as they are published
by workflow nodes.

*Operation ID*: `stream_workflow_events_api_v1_workflow_exec__session_id__stream_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `session_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/workflow-exec/{workflow_id}/start`

**Start Workflow**

Start executing a workflow definition.

Loads the WorkflowDefinition from the repository, compiles it into
a LangGraph StateGraph, builds the initial state, and launches
the execution as a background task.

*Operation ID*: `start_workflow_api_v1_workflow_exec__workflow_id__start_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `workflow_id` | path | string | ✓ |  |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/workflow-exec/{workflow_id}/start`

**Start Workflow**

Start executing a workflow definition.

Loads the WorkflowDefinition from the repository, compiles it into
a LangGraph StateGraph, builds the initial state, and launches
the execution as a background task.

*Operation ID*: `start_workflow_api_v1_workflow_exec__workflow_id__start_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `workflow_id` | path | string | ✓ |  |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

## workflow-templates

### `GET` `/api/v1/workflow-templates`

**List Workflow Templates**

List all workflow templates (system + custom + modules), filterable by category.

*Operation ID*: `list_workflow_templates_api_v1_workflow_templates_get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `category` | query | string |  |  |
| `limit` | query | integer |  |  |
| `offset` | query | integer |  |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/workflow-templates`

**Create Workflow Template**

Create a new custom workflow template.

``is_system`` is always forced to ``False`` for API-created templates.

*Operation ID*: `create_workflow_template_api_v1_workflow_templates_post`

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `201` | Successful Response |
| `422` | Validation Error |

---

### `DELETE` `/api/v1/workflow-templates/{template_id}`

**Delete Workflow Template**

Delete a workflow template.

System templates cannot be deleted (HTTP 403).

*Operation ID*: `delete_workflow_template_api_v1_workflow_templates__template_id__delete`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `template_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` `/api/v1/workflow-templates/{template_id}`

**Get Workflow Template**

Get a single workflow template by ID.

*Operation ID*: `get_workflow_template_api_v1_workflow_templates__template_id__get`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `template_id` | path | string | ✓ |  |

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `PUT` `/api/v1/workflow-templates/{template_id}`

**Update Workflow Template**

Update an existing workflow template.

System templates cannot be updated (HTTP 403).

*Operation ID*: `update_workflow_template_api_v1_workflow_templates__template_id__put`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `template_id` | path | string | ✓ |  |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` `/api/v1/workflow-templates/{template_id}/instantiate`

**Instantiate Workflow Template**

Instantiate a workflow template into a concrete WorkflowDefinition.

1. Load the template.
2. Replace all {{key}} placeholders with provided values.
3. Validate blueprint_ref placeholders against the catalog.
4. Validate the resulting graph structure.
5. Create and persist a new WorkflowDefinition.

*Operation ID*: `instantiate_workflow_template_api_v1_workflow_templates__template_id__instantiate_post`

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `template_id` | path | string | ✓ |  |

**Request Body:**

**Responses:**

| Status | Description |
|--------|-------------|
| `201` | Successful Response |
| `422` | Validation Error |

---

## Schema Definitions

### Data Model: `A2AAgentConfig`

Configuration for an external A2A agent participating in the debate.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `position` | string |  | Where to insert the A2A agent: 'after_all', 'after:critic', 'before:moderator', etc. |
| `role` | string |  | Role name for the A2A agent in the debate |
| `url` | string | ✓ | A2A agent URL |

---

### Data Model: `AgentBlueprint`

A reusable agent configuration combining LLM, role, and prompt.

The composite model — ties together an LLM profile, a role definition,
and optionally a prompt template into a reusable debate agent
configuration.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `created_at` | string |  |  |
| `description` | string |  |  |
| `id` | string | ✓ |  |
| `is_active` | boolean |  |  |
| `llm_profile_id` | string | ✓ |  |
| `name` | string | ✓ |  |
| `prompt_template_id` | string |  |  |
| `role_definition_id` | string | ✓ |  |
| `tags` | array[string] |  |  |
| `tts_voice_id` | string |  |  |
| `updated_at` | string |  |  |

---

### Data Model: `AgentBundle`

A reusable composition of LLM + Role-Type + Persona + Prompt + Tone Profile.

Represents a complete debate agent configuration that can be placed
as a node on the Canvas and referenced in Workflows.  Unlike
``AgentBlueprint`` (which ties LLM + RoleDefinition + PromptTemplate
together), a Bundle is more flexible: it references a RoleType directly
and optionally includes a ToneProfile.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `created_at` | string |  |  |
| `description` | string |  |  |
| `id` | string |  |  |
| `is_active` | boolean |  |  |
| `llm_profile_id` | string | ✓ |  |
| `name` | string | ✓ |  |
| `persona_id` | string |  |  |
| `prompt_template_id` | string |  |  |
| `role_definition_id` | string |  |  |
| `role_type_id` | string | ✓ |  |
| `tags` | array[string] |  |  |
| `tone_profile_id` | string |  |  |
| `updated_at` | string |  |  |

---

### Data Model: `AgentConfig`

Configuration for a single debate agent.

The ``role`` field accepts any string (typically a RoleType.id).
For backward compatibility, legacy AgentRole enum values are also accepted.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `llm_profile` | string |  |  |
| `role` | string | ✓ |  |
| `temperature` | number |  |  |

---

### Data Model: `AgentOutput`

Output produced by one agent in one round.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `content` | string | ✓ |  |
| `role` | string | ✓ |  |
| `tokens_used` | integer |  |  |

---

### Data Model: `AgentPersona`

Configuration for a debate agent persona.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `argumentation_pattern` | string |  |  |
| `consensus_threshold` | number |  |  |
| `description` | string |  |  |
| `id` | string | ✓ |  |
| `llm_profile_id` | string | ✓ |  |
| `max_rounds` | integer |  |  |
| `mode` | string |  |  |
| `name` | string | ✓ |  |
| `role` | string | ✓ |  |
| `system_prompt` | string | ✓ |  |
| `tags` | array[string] |  |  |

---

### Data Model: `ApproveResponse`

Response after approving a proposal.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `new_version_id` | string | ✓ |  |
| `proposal_id` | string | ✓ |  |
| `status` | string |  |  |

---

### Data Model: `ApproveTranslationRequest`

Request body for manual translation approval.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `approved` | boolean |  | Set to True to approve, False to reject |
| `file_path` | string | ✓ | File path of the translation |

---

### Data Model: `BackupCreateBody`

Request body to create a backup.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `trigger` | string |  |  |

---

### Data Model: `BackupRestoreBody`

Request body to restore a backup.

.. warning::
    This operation is destructive and overwrites existing data.
    The function is a placeholder and not yet implemented.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `backup_id` | string | ✓ |  |

---

### Data Model: `BackupSettingsBody`

Request body for backup settings update.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `backup_auto_on_shutdown` | string |  |  |
| `backup_dir` | string |  |  |
| `backup_enabled` | string |  |  |
| `backup_encrypt` | string |  |  |
| `backup_retention_count` | string |  |  |

---

### Data Model: `BatchTranslateRequest`

Request body for batch translation of multiple modules.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `force` | boolean |  | Force re-translation even if cached |
| `module_ids` | array[string] | ✓ | List of module IDs to translate |
| `parallel` | boolean |  | Translate modules in parallel (requires async support) |
| `target_language` | string | ✓ | Target language code |

---

### Data Model: `BlueprintLLMProfile`

LLM configuration for use in Agent Blueprints.

Extends the concept of ``backend.core.profiles.LLMProfile`` with
blueprint-specific metadata (description, tags, timestamps).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `a2a_config` | object |  |  |
| `a2a_endpoint` | string |  |  |
| `a2a_timeout` | integer |  |  |
| `api_base` | string |  |  |
| `api_key_env` | string |  |  |
| `context_window` | string |  |  |
| `cost_per_1k_input` | string |  |  |
| `cost_per_1k_output` | string |  |  |
| `created_at` | string |  |  |
| `description` | string |  |  |
| `fallback_llm_profile_id` | string |  |  |
| `id` | string | ✓ |  |
| `max_tokens` | integer |  |  |
| `model` | string | ✓ |  |
| `name` | string | ✓ |  |
| `profile_type` | enum(text, tts, stt) |  |  |
| `protocol` | enum(litellm, a2a, stt) |  |  |
| `provider` | enum(openrouter, openai, anthropic, local, ollama, opencode-zen, opencode-go, xiaomi, whisper-local, whisper-api, azure-stt, google-stt) | ✓ |  |
| `service_eligible` | boolean |  |  |
| `tags` | array[string] |  |  |
| `temperature` | number |  |  |
| `timeout` | integer |  |  |
| `updated_at` | string |  |  |

---

### Data Model: `Body_upload_document_api_v1_dms_documents_post`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | string | ✓ |  |

---

### Data Model: `BulkTranslateRequest`

Request for batch LLM translation.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `force` | boolean |  |  |
| `namespace` | string |  |  |
| `target_locales` | string |  |  |

---

### Data Model: `BulkTranslationRequest`

Bulk-set translations for a locale.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `locale` | string | ✓ |  |
| `namespace` | string |  |  |
| `translations` | object | ✓ |  |

---

### Data Model: `CanvasLayout-Input`

A saved canvas arrangement of agent blueprints.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `created_at` | string |  |  |
| `description` | string |  |  |
| `id` | string |  |  |
| `layout_data` | [CanvasLayoutData](#data-model-canvaslayoutdata) |  |  |
| `name` | string | ✓ |  |
| `project_id` | string |  |  |
| `updated_at` | string |  |  |

---

### Data Model: `CanvasLayout-Output`

A saved canvas arrangement of agent blueprints.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `created_at` | string |  |  |
| `description` | string |  |  |
| `id` | string |  |  |
| `layout_data` | [CanvasLayoutData](#data-model-canvaslayoutdata) |  |  |
| `name` | string | ✓ |  |
| `project_id` | string |  |  |
| `updated_at` | string |  |  |

---

### Data Model: `CanvasLayoutData`

Simplified canvas layout data — NOT raw React Flow JSON.

Translation to full Svelte Flow format happens in the frontend on load.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `edges` | array[[CanvasLayoutEdge](#data-model-canvaslayoutedge)] |  |  |
| `nodes` | array[[CanvasLayoutNode](#data-model-canvaslayoutnode)] |  |  |
| `viewport` | [CanvasLayoutViewport](#data-model-canvaslayoutviewport) |  |  |

---

### Data Model: `CanvasLayoutEdge`

An edge in the simplified canvas layout format.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `data` | object |  |  |
| `id` | string | ✓ |  |
| `source` | string | ✓ |  |
| `source_handle` | string |  |  |
| `target` | string | ✓ |  |
| `target_handle` | string |  |  |
| `type` | string |  |  |

---

### Data Model: `CanvasLayoutNode`

A node in the simplified canvas layout format.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agent_blueprint_id` | string |  |  |
| `blueprint_id` | string |  |  |
| `config` | object |  |  |
| `data` | object |  |  |
| `id` | string | ✓ |  |
| `label` | string |  |  |
| `type` | string | ✓ |  |
| `x` | number |  |  |
| `y` | number |  |  |

---

### Data Model: `CanvasLayoutViewport`

Viewport state for the canvas.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `x` | number |  |  |
| `y` | number |  |  |
| `zoom` | number |  |  |

---

### Data Model: `CapabilitiesRequest`

Request body for storing A2A capabilities.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `capabilities` | object | ✓ | Discovered capabilities from A2A agent |

---

### Data Model: `CaseInput`

The case or topic to debate.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `project_id` | string |  |  |
| `text` | string | ✓ | Case description |

---

### Data Model: `CompilationResult`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `errors` | array[string] |  |  |
| `is_valid` | boolean | ✓ |  |
| `resolved_agents` | array[[ResolvedAgent](#data-model-resolvedagent)] |  |  |
| `warnings` | array[string] |  |  |

---

### Data Model: `ConditionalEdge`

An edge with a condition expression for branching logic.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `condition` | string | ✓ |  |
| `description` | string |  |  |
| `source_node_id` | string | ✓ |  |
| `target_node_id` | string | ✓ |  |

---

### Data Model: `ConvertToWorkflowRequest`

Request body for converting a canvas layout to a workflow definition.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `consensus_threshold` | number |  | Default consensus threshold for termination condition |
| `description` | string |  | Optional workflow description |
| `max_rounds` | integer |  | Default max rounds for termination condition |
| `name` | string |  | Workflow name (defaults to layout name) |

---

### Data Model: `CreatePromptVariantRequest`

Request body for creating a prompt variant.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `description` | string |  |  |
| `id` | string | ✓ |  |
| `name` | string | ✓ |  |
| `prompts` | object |  | Role → prompt content mapping (e.g. {"strategist": "...", "critic": "..."}) |

---

### Data Model: `CreateRenderRequest`

Request body for starting a render job.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `config` | object |  | Plugin-specific configuration |
| `plugin_key` | string | ✓ | Key of the output plugin (e.g. 'print', 'tts') |

---

### Data Model: `CreateRenderResponse`

Response after creating a render job.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `job_id` | string | ✓ |  |
| `plugin_key` | string | ✓ |  |
| `session_id` | string | ✓ |  |
| `status` | string |  |  |

---

### Data Model: `CreateReportRequest`

Request body for creating a report job.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `format` | string |  | Output format: 'docx', 'pdf', or 'odf' |

---

### Data Model: `CreateReportResponse`

Response after creating a report job.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `format` | string | ✓ |  |
| `job_id` | string | ✓ |  |
| `status` | string |  |  |

---

### Data Model: `DebateContinueBody`

POST /api/v1/debate/{id}/continue request body.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `focus_topic` | string |  |  |
| `new_title` | string |  |  |

---

### Data Model: `DebateListItem`

GET /api/v1/debate list item — lightweight summary for history.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `case_preview` | string |  |  |
| `case_text` | string |  |  |
| `consensus_score` | string |  |  |
| `created_at` | string | ✓ |  |
| `current_round` | integer |  |  |
| `debate_id` | string | ✓ |  |
| `forks_count` | integer |  |  |
| `language` | string |  |  |
| `max_rounds` | integer |  |  |
| `parent_debate_id` | string |  |  |
| `project_id` | string |  |  |
| `project_name` | string |  |  |
| `status` | [DebateStatus](#data-model-debatestatus) | ✓ |  |
| `title` | string |  |  |
| `updated_at` | string | ✓ |  |

---

### Data Model: `DebateRequest`

POST /api/v1/debate request body.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `a2a_agents` | array[[A2AAgentConfig](#data-model-a2aagentconfig)] |  | External A2A agents to include as debate participants |
| `agent_persona_ids` | object |  | Mapping of agent role to persona ID (e.g. {'strategist': 'strategist-default'}) |
| `agent_profile` | array[[AgentConfig](#data-model-agentconfig)] |  | List of agent configurations. Each role is a RoleType.id. Default: legacy 4-role setup (strategist, critic, optimizer, moderator). For custom roles, provide explicit list with bundle_id references. |
| `bundle_ids` | array[string] |  | AgentBundle IDs to use for debate agents. If provided, overrides agent_profile defaults. |
| `case` | [CaseInput](#data-model-caseinput) | ✓ |  |
| `consensus_threshold` | number |  |  |
| `document_ids` | array[string] |  | List of DMS document IDs to include as RAG context for this debate |
| `enable_extra_rounds` | boolean |  | If true, the moderator can request additional rounds when consensus is not reached |
| `enable_fact_check` | boolean |  |  |
| `enable_memory` | boolean |  |  |
| `include_debate_results` | boolean |  | If true, include results from previous completed debates as RAG context |
| `language` | string |  | Language for debate prompts: 'de' (German) or 'en' (English) |
| `llm_profile_id` | string |  | LLM profile to use |
| `max_rounds` | integer |  |  |
| `prompt_variant` | string |  | Prompt variant ID |
| `rag_auto_retrieve` | boolean |  | If true, automatically retrieve relevant document chunks based on the case text |
| `search_mode` | [SearchMode](#data-model-searchmode) |  | Web search mode: 'off', 'optional', or 'required' |

---

### Data Model: `DebateResponse`

POST /api/v1/debate response.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `created_at` | string |  |  |
| `debate_id` | string | ✓ |  |
| `status` | [DebateStatus](#data-model-debatestatus) |  |  |
| `title` | string |  |  |

---

### Data Model: `DebateStatus`

**Values**: `pending, running, completed, failed`

---

### Data Model: `DebateStatusResponse`

GET /api/v1/debate/{id} response.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `anomalies` | array[string] |  |  |
| `case_text` | string |  |  |
| `consensus_score` | string |  |  |
| `created_at` | string | ✓ |  |
| `current_round` | integer |  |  |
| `debate_id` | string | ✓ |  |
| `forks_count` | integer |  |  |
| `has_active_interrupt` | boolean |  |  |
| `hitl_enabled` | boolean |  |  |
| `hitl_mode` | string |  |  |
| `is_paused` | boolean |  |  |
| `language` | string |  |  |
| `llm_profile_id` | string |  |  |
| `llm_profile_model` | string |  |  |
| `max_rounds` | integer |  |  |
| `parent_debate_id` | string |  |  |
| `project_id` | string |  |  |
| `project_name` | string |  |  |
| `rag_context_preview` | string |  |  |
| `rag_document_count` | integer |  |  |
| `rag_enabled` | boolean |  |  |
| `rounds` | array[[RoundData](#data-model-rounddata)] |  |  |
| `status` | [DebateStatus](#data-model-debatestatus) | ✓ |  |
| `title` | string |  |  |
| `total_interactions` | integer |  |  |
| `updated_at` | string | ✓ |  |

---

### Data Model: `DiscoverRequest`

Request body for A2A discovery.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `endpoint_url` | string | ✓ | A2A agent endpoint URL |

---

### Data Model: `DocumentAssignment`

Request body for assigning documents to a debate.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `document_ids` | array[string] | ✓ |  |
| `rag_auto_retrieve` | boolean |  |  |

---

### Data Model: `DuplicateRequest`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `new_id` | string | ✓ | New module ID |
| `new_name` | string |  | Optional new display name |

---

### Data Model: `ExtensionDecision`

Decision on whether to grant extra debate rounds.

**Values**: `pending, granted, denied, timeout`

---

### Data Model: `ExtensionDecisionModel`

POST /debate/{id}/extension-decision — user/player decides on extension.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `decision` | [ExtensionDecision](#data-model-extensiondecision) | ✓ | GRANTED to allow extra rounds, DENIED to end debate |

---

### Data Model: `ExtensionRequest`

POST /debate/{id}/extension-request — moderator requests extra rounds.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `current_consensus` | number | ✓ | Current consensus score |
| `current_round` | integer | ✓ | Current round number |
| `max_rounds` | integer | ✓ | Configured max rounds |
| `threshold` | number | ✓ | Consensus threshold |

---

### Data Model: `ExtensionResponse`

Response after submitting an extension decision.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `debate_id` | string | ✓ |  |
| `decision` | [ExtensionDecision](#data-model-extensiondecision) | ✓ |  |
| `message` | string |  |  |
| `new_max_rounds` | integer | ✓ |  |

---

### Data Model: `ForkDebateBody`

POST /api/v1/debate/{id}/fork request body.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `fork_from_round` | string |  |  |
| `fork_reason` | string |  |  |
| `modified_personas` | string |  |  |
| `modified_prompt_variant` | string |  |  |
| `new_title` | string | ✓ |  |

---

### Data Model: `ForkFromConsensusBody`

POST /api/v1/debate/{id}/fork-from-consensus request body.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `consensus_threshold` | number |  |  |
| `inherit_llm_profile` | boolean |  |  |
| `inherit_personas` | boolean |  |  |
| `max_rounds` | integer |  |  |
| `new_title` | string | ✓ |  |
| `new_topic` | string | ✓ |  |

---

### Data Model: `HITLMode`

HITL operation mode.

**Values**: `full, inject_only, query_only, off`

---

### Data Model: `HITLStatusResponse`

GET /debate/{id}/hitl/status — current HITL state.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `active_interrupt` | string |  |  |
| `debate_id` | string | ✓ |  |
| `hitl_enabled` | boolean | ✓ |  |
| `hitl_mode` | [HITLMode](#data-model-hitlmode) | ✓ |  |
| `interactions_by_type` | object |  |  |
| `is_paused` | boolean |  |  |
| `max_interrupts_per_round` | integer |  |  |
| `round_interrupt_count` | integer |  |  |
| `total_interactions` | integer |  |  |

---

### Data Model: `HTTPValidationError`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `detail` | array[[ValidationError](#data-model-validationerror)] |  |  |

---

### Data Model: `HealthResponse`

GET /health response.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `status` | string |  |  |
| `version` | string | ✓ |  |

---

### Data Model: `ImportBundleRequest`

Request body for importing a bundle.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `conflict_strategy` | string |  |  |
| `data` | object | ✓ |  |

---

### Data Model: `ImportResult`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `created` | integer |  |  |
| `errors` | array[string] |  |  |
| `skipped` | integer |  |  |
| `updated` | integer |  |  |

---

### Data Model: `InjectRequest`

POST /debate/{id}/inject — user injects context into running debate.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `content` | string | ✓ | Context or information to inject into the debate |
| `priority` | string |  | Injection priority: 'low', 'normal', 'high', 'urgent' |
| `target_agent` | string |  | Target agent role (e.g. 'critic'). If None, injected to all future agents in the current and subsequent rounds. |
| `target_round` | string |  | Target round number. If None, applies to current and future rounds. |

---

### Data Model: `InjectResponse`

Response after submitting an inject.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `interaction_id` | string | ✓ |  |
| `message` | string |  |  |
| `status` | string |  |  |
| `target_resolved` | string |  |  |

---

### Data Model: `InputJobStatusResponse`

Response for input job status query.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `completed_at` | string |  |  |
| `created_at` | string | ✓ |  |
| `error_message` | string |  |  |
| `job_id` | string | ✓ |  |
| `plugin_key` | string | ✓ |  |
| `processed_input` | string |  |  |
| `status` | string | ✓ |  |

---

### Data Model: `InputPluginInfo`

Information about a registered input plugin.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `config_schema` | object | ✓ | JSON Schema for the plugin's config |
| `plugin_key` | string | ✓ |  |
| `plugin_name` | string | ✓ |  |
| `ui_hints` | object |  | Frontend metadata (requires_microphone, supports_streaming, etc.) |

---

### Data Model: `InstallRequest`

Request body for module installation.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `module_id` | string | ✓ | Module ID to install |
| `overwrite` | boolean |  | Overwrite existing installation |
| `source` | string |  | Source: 'local' or 'url' |
| `source_url` | string |  | URL for remote installation |

---

### Data Model: `InstantiateRequest`

Request body for template instantiation.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string |  |  |
| `placeholder_values` | object |  |  |

---

### Data Model: `InteractionDirection`

Direction of HITL interaction.

**Values**: `user_to_agent, agent_to_user`

---

### Data Model: `InteractionListResponse`

GET /debate/{id}/interactions — paginated interaction history.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `interactions` | array[[InteractionResponse](#data-model-interactionresponse)] |  |  |
| `limit` | integer |  |  |
| `offset` | integer |  |  |
| `total` | integer |  |  |

---

### Data Model: `InteractionResponse`

A single interaction record returned by the API.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agent_index` | integer | ✓ |  |
| `content` | string | ✓ |  |
| `direction` | [InteractionDirection](#data-model-interactiondirection) | ✓ |  |
| `interaction_id` | string | ✓ |  |
| `metadata` | object |  |  |
| `round` | integer | ✓ |  |
| `source` | string | ✓ |  |
| `status` | [InteractionStatus](#data-model-interactionstatus) | ✓ |  |
| `target` | string | ✓ |  |
| `timestamp` | string | ✓ |  |
| `type` | [InteractionType](#data-model-interactiontype) | ✓ |  |

---

### Data Model: `InteractionStatus`

Lifecycle status of an interaction.

**Values**: `pending, delivered, consumed, expired`

---

### Data Model: `InteractionType`

Type of HITL interaction.

**Values**: `inject, query, response`

---

### Data Model: `InterjectRequest`

Request body for submitting an interjection.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `content` | string | ✓ | The interjection text |
| `metadata` | object |  | Optional metadata |
| `source` | string |  | Origin of the interjection (user, system, api) |

---

### Data Model: `InterjectResponse`

Response after submitting an interjection.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `interjection_id` | string | ✓ |  |
| `status` | string |  |  |

---

### Data Model: `InterjectionPoint`

A node that accepts external input during workflow execution.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `blocking` | boolean |  |  |
| `description` | string |  |  |
| `input_type` | enum(user_query, oob_input, external_event) |  |  |
| `node_id` | string | ✓ |  |

---

### Data Model: `InterruptInfo`

Information about an active interrupt (agent waiting for user).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agent_role` | string | ✓ |  |
| `context` | string |  |  |
| `created_at` | string | ✓ |  |
| `elapsed_seconds` | number |  |  |
| `interrupt_id` | string | ✓ |  |
| `question` | string | ✓ |  |
| `round` | integer | ✓ |  |
| `status` | [InterruptStatus](#data-model-interruptstatus) | ✓ |  |
| `timeout_seconds` | integer | ✓ |  |

---

### Data Model: `InterruptStatus`

Status of an active interrupt.

**Values**: `waiting, answered, timeout, cancelled`

---

### Data Model: `InvalidateTranslationRequest`

Request body for invalidating cached translations.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file_path` | string |  | Specific file to invalidate (None = all files) |
| `target_language` | string |  | Specific language to invalidate (None = all languages) |

---

### Data Model: `LLMProfile`

Configuration for a specific LLM endpoint.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `a2a_endpoint` | string |  |  |
| `a2a_timeout` | integer |  |  |
| `api_base` | string |  |  |
| `api_key_env` | string |  |  |
| `context_window` | string |  |  |
| `cost_per_1k_input` | string |  |  |
| `cost_per_1k_output` | string |  |  |
| `fallback_llm_profile_id` | string |  |  |
| `id` | string | ✓ |  |
| `max_tokens` | integer |  |  |
| `min_recommended_context` | integer |  |  |
| `model` | string | ✓ |  |
| `name` | string | ✓ |  |
| `profile_type` | enum(text, tts, stt) |  |  |
| `protocol` | enum(litellm, a2a) |  |  |
| `provider` | [LLMProvider](#data-model-llmprovider) | ✓ |  |
| `service_eligible` | boolean |  |  |
| `temperature` | number |  |  |
| `timeout` | integer |  |  |

---

### Data Model: `LLMProvider`

Supported LLM providers.

**Values**: `openrouter, openai, anthropic, local, ollama, opencode-zen, opencode-go, xiaomi`

---

### Data Model: `LanguageBody`

Language update body.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `language` | string | ✓ |  |

---

### Data Model: `LanguagePackExportRequest`

Request to export UI translations as a Language Pack ZIP.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `author` | string |  |  |
| `description` | string |  |  |
| `name` | string |  |  |
| `pack_id_suffix` | string |  |  |

---

### Data Model: `LaunchWorkflowRequest`

Request body for launching a workflow from a completed input job.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `consensus_threshold` | number |  |  |
| `job_id` | string | ✓ | InputJob ID (must have status=completed) |
| `language` | string |  | Language code |
| `max_rounds` | integer |  |  |
| `project_id` | string |  | Project ID |
| `workflow_id` | string |  | WorkflowDefinition ID to execute. If omitted, uses workflow_template_id or first available active workflow. |
| `workflow_template_id` | string |  | WorkflowTemplate ID to instantiate into a WorkflowDefinition. Ignored if workflow_id is provided. |

---

### Data Model: `LaunchWorkflowResponse`

Response after launching a workflow from input.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | string | ✓ |  |
| `status` | string | ✓ |  |
| `workflow_id` | string | ✓ |  |

---

### Data Model: `OOBInputBody`

POST /api/v1/debate/{id}/oob request body.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `content` | string | ✓ | Additional context |
| `target` | [OOBTarget](#data-model-oobtarget) | ✓ |  |
| `urgency` | string |  |  |

---

### Data Model: `OOBInputResponse`

Response after submitting an OOB input.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `oob_id` | string | ✓ |  |
| `status` | string |  |  |
| `target_resolved` | string |  |  |

---

### Data Model: `OOBTarget`

Routing target for an OOB input.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agent_role` | string |  |  |
| `current_agent_role` | string |  |  |
| `from_round` | string |  |  |
| `round` | string |  |  |
| `type` | [OOBTargetType](#data-model-oobtargettype) | ✓ |  |

---

### Data Model: `OOBTargetType`

Target type for OOB input routing.

**Values**: `specific_agent, next_agent, all_future, current_active`

---

### Data Model: `PauseAction`

Pause/resume action.

**Values**: `pause, resume`

---

### Data Model: `PauseRequest`

POST /debate/{id}/pause — pause or resume a running debate.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `action` | [PauseAction](#data-model-pauseaction) | ✓ | 'pause' to pause the debate, 'resume' to continue |
| `reason` | string |  | Optional reason for pausing |

---

### Data Model: `PauseResponse`

Response after pause/resume action.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `action` | [PauseAction](#data-model-pauseaction) | ✓ |  |
| `debate_id` | string | ✓ |  |
| `message` | string |  |  |
| `paused` | boolean | ✓ |  |

---

### Data Model: `PluginInfo`

Information about a registered output plugin.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `config_schema` | object | ✓ | JSON Schema for the plugin's config, usable for dynamic form generation |
| `plugin_key` | string | ✓ |  |
| `plugin_name` | string | ✓ |  |
| `supported_formats` | array[string] | ✓ |  |

---

### Data Model: `ProfileUpdateRequest`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `data` | object | ✓ |  |

---

### Data Model: `ProjectConfig-Input`

Project-specific settings with optional overrides.

``None`` values fall back to global defaults.  Profile overrides use a
merge strategy: project profiles supplement global ones, and when an ID
exists in both, the project version wins.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agent_personas` | object |  |  |
| `default_consensus_threshold` | string |  |  |
| `default_max_rounds` | string |  |  |
| `language` | string |  |  |
| `llm_profiles` | object |  |  |
| `prompt_variants` | object |  |  |
| `search_mode` | string |  |  |
| `searxng_url` | string |  |  |

---

### Data Model: `ProjectConfig-Output`

Project-specific settings with optional overrides.

``None`` values fall back to global defaults.  Profile overrides use a
merge strategy: project profiles supplement global ones, and when an ID
exists in both, the project version wins.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agent_personas` | object |  |  |
| `default_consensus_threshold` | string |  |  |
| `default_max_rounds` | string |  |  |
| `language` | string |  |  |
| `llm_profiles` | object |  |  |
| `prompt_variants` | object |  |  |
| `search_mode` | string |  |  |
| `searxng_url` | string |  |  |

---

### Data Model: `ProjectConfigUpdateRequest`

PUT /api/v1/projects/{id}/config request body.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `config` | [ProjectConfig-Input](#data-model-projectconfig-input) | ✓ |  |

---

### Data Model: `ProjectCreateRequest`

POST /api/v1/projects request body.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `description` | string |  |  |
| `name` | string | ✓ |  |

---

### Data Model: `ProjectListItem`

GET /api/v1/projects list item — lightweight summary.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `created_at` | string | ✓ |  |
| `description` | string | ✓ |  |
| `id` | string | ✓ |  |
| `is_system` | boolean | ✓ |  |
| `name` | string | ✓ |  |
| `updated_at` | string | ✓ |  |

---

### Data Model: `ProjectResponse`

GET /api/v1/projects/{id} response.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `config` | [ProjectConfig-Output](#data-model-projectconfig-output) | ✓ |  |
| `created_at` | string | ✓ |  |
| `description` | string | ✓ |  |
| `id` | string | ✓ |  |
| `is_system` | boolean | ✓ |  |
| `name` | string | ✓ |  |
| `updated_at` | string | ✓ |  |

---

### Data Model: `ProjectUpdateRequest`

PUT /api/v1/projects/{id} request body.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `description` | string |  |  |
| `name` | string |  |  |

---

### Data Model: `PromptTemplate`

A named prompt template with content and metadata.

Replaces the file-path-only approach of
``backend.core.profiles.PromptVariant``.  Content is stored inline
in the database rather than referencing files.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `content` | string | ✓ |  |
| `content_hash` | string |  |  |
| `created_at` | string |  |  |
| `description` | string |  |  |
| `id` | string | ✓ |  |
| `language` | string |  |  |
| `name` | string | ✓ |  |
| `role` | string |  |  |
| `source_path` | string |  |  |
| `tags` | array[string] |  |  |
| `updated_at` | string |  |  |
| `variant` | string |  |  |

---

### Data Model: `PromptVariant`

A named set of prompt templates for debate agents.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `base_path` | string | ✓ |  |
| `description` | string |  |  |
| `id` | string | ✓ |  |
| `name` | string | ✓ |  |
| `overrides` | object |  |  |
| `parent_variant` | string |  |  |

---

### Data Model: `ProposalResponse`

Response model for an optimization proposal.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `approved_at` | string |  |  |
| `approved_by` | string |  |  |
| `created_at` | string | ✓ |  |
| `created_by` | string | ✓ |  |
| `estimated_impact` | string |  |  |
| `id` | string | ✓ |  |
| `new_version_id` | string |  |  |
| `parent_version_id` | string |  |  |
| `proposed_edges` | array[object] |  |  |
| `proposed_nodes` | array[object] |  |  |
| `rationale` | string |  |  |
| `risk_assessment` | string |  |  |
| `source_session_id` | string |  |  |
| `status` | string | ✓ |  |
| `target_workflow_id` | string | ✓ |  |

---

### Data Model: `ReflectResponse`

Response after generating a proposal.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `proposal_id` | string | ✓ |  |
| `status` | string |  |  |
| `target_workflow_id` | string | ✓ |  |

---

### Data Model: `RegisterLocaleRequest`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `is_rtl` | boolean |  |  |
| `locale` | string | ✓ |  |
| `name` | string |  |  |

---

### Data Model: `RenderJobStatusResponse`

Response for render job status query.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `completed_at` | string |  |  |
| `created_at` | string | ✓ |  |
| `error_message` | string |  |  |
| `job_id` | string | ✓ |  |
| `output_files` | array[string] |  |  |
| `plugin_key` | string | ✓ |  |
| `session_id` | string | ✓ |  |
| `started_at` | string |  |  |
| `status` | string | ✓ |  |

---

### Data Model: `ReportStatusResponse`

Response for report job status query.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `completed_at` | string |  |  |
| `created_at` | string | ✓ |  |
| `error` | string |  |  |
| `file_path` | string |  |  |
| `format` | string | ✓ |  |
| `job_id` | string | ✓ |  |
| `session_id` | string | ✓ |  |
| `status` | string | ✓ |  |

---

### Data Model: `ResolvedAgent`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `argumentation_pattern` | string |  |  |
| `blueprint_id` | string | ✓ |  |
| `blueprint_name` | string | ✓ |  |
| `default_consensus_threshold` | number |  |  |
| `default_max_rounds` | integer |  |  |
| `llm_model` | string | ✓ |  |
| `llm_profile_id` | string | ✓ |  |
| `mode` | string |  |  |
| `node_id` | string | ✓ |  |
| `prompt_template_id` | string | ✓ |  |
| `role` | string | ✓ |  |
| `role_definition_id` | string | ✓ |  |
| `role_type_color` | string |  |  |
| `role_type_icon` | string |  |  |
| `role_type_name` | string |  |  |

---

### Data Model: `ResolvedBundle`

An AgentBundle with all referenced entities resolved and inline.

Produced by the BundleResolver for use in Workflow execution.
Contains the fully assembled system prompt.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `bundle_id` | string | ✓ |  |
| `bundle_name` | string | ✓ |  |
| `llm_profile` | [BlueprintLLMProfile](#data-model-blueprintllmprofile) | ✓ |  |
| `prompt_template` | string |  |  |
| `role_definition` | string |  |  |
| `role_type` | [RoleType](#data-model-roletype) | ✓ |  |
| `system_prompt` | string |  |  |
| `tone_profile` | string |  |  |

---

### Data Model: `RespondRequest`

POST /debate/{id}/respond — user responds to an agent query.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `interrupt_id` | string | ✓ | ID of the interrupt (agent query) being answered |
| `response` | string | ✓ | User's response to the agent's question |

---

### Data Model: `RespondResponse`

Response after answering an agent query.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `interaction_id` | string | ✓ |  |
| `interrupt_id` | string | ✓ |  |
| `message` | string |  |  |
| `status` | string |  |  |

---

### Data Model: `RoleDefinition`

Defines an agent role with behavior constraints and prompt reference.

Extends ``backend.core.profiles.AgentPersona`` with richer metadata
and a decoupled prompt reference (by ID, not inline text).

The ``role_type_id`` field references a ``RoleType.id``, allowing
dynamic role types beyond the hardcoded strategist/critic/optimizer/moderator.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `argumentation_pattern` | string |  |  |
| `consensus_threshold` | number |  |  |
| `created_at` | string |  |  |
| `description` | string |  |  |
| `id` | string | ✓ |  |
| `max_rounds` | integer |  |  |
| `mode` | string |  |  |
| `name` | string | ✓ |  |
| `prompt_template_id` | string |  |  |
| `role_type_id` | string |  |  |
| `tags` | array[string] |  |  |
| `updated_at` | string |  |  |

---

### Data Model: `RoleType`

A configurable role type/category (e.g. strategist, critic, optimizer, moderator).

Role types are first-class canvas entities that can be created, edited,
and connected to Role Definitions and Agent Blueprints. They define the
behavioral category and visual identity of a role.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `category` | enum(functional, formative) |  |  |
| `color` | string |  |  |
| `created_at` | string |  |  |
| `default_consensus_threshold` | number |  |  |
| `default_max_rounds` | integer |  |  |
| `description` | string |  |  |
| `icon` | string |  |  |
| `id` | string | ✓ |  |
| `is_active` | boolean |  |  |
| `name` | string | ✓ |  |
| `tags` | array[string] |  |  |
| `updated_at` | string |  |  |

---

### Data Model: `RoundData`

Data for a single debate round.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agent_outputs` | array[[AgentOutput](#data-model-agentoutput)] |  |  |
| `consensus` | number |  |  |
| `round` | integer | ✓ |  |

---

### Data Model: `SearchMode`

Web search mode for a debate.

**Values**: `off, optional, required`

---

### Data Model: `SessionStateResponse`

Response for session state query.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `current_node_id` | string |  |  |
| `current_round` | integer |  |  |
| `final_consensus` | string |  |  |
| `node_outputs` | array[object] |  |  |
| `output` | string |  |  |
| `session_id` | string | ✓ |  |
| `status` | string | ✓ |  |
| `workflow_id` | string |  |  |

---

### Data Model: `StartFromLayoutBody`

Request body for starting a debate from a canvas layout.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `bundle_ids` | array[string] |  | AgentBundle IDs to use (overrides layout agent nodes) |
| `case_text` | string | ✓ | Debate case/topic |
| `consensus_threshold` | number |  |  |
| `language` | string |  |  |
| `llm_profile_id` | string |  |  |
| `max_rounds` | integer |  |  |

---

### Data Model: `StartFromWorkflowBody`

Request body for starting a debate from a workflow definition.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `case_text` | string | ✓ | Debate case/topic |
| `consensus_threshold` | number |  |  |
| `language` | string |  |  |
| `max_rounds` | integer |  |  |

---

### Data Model: `StartWorkflowRequest`

Request body for starting a workflow.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `context` | string | ✓ | The debate topic / context |
| `document_ids` | array[string] |  | DMS document IDs to include as RAG context |
| `language` | string |  | Language code |
| `max_rounds` | integer |  | Maximum rounds |
| `project_id` | string |  | Project ID |
| `rag_auto_retrieve` | boolean |  | Automatically retrieve relevant document chunks based on context |
| `threshold` | number |  | Consensus threshold |

---

### Data Model: `StartWorkflowResponse`

Response after starting a workflow.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | string | ✓ |  |
| `status` | string |  |  |

---

### Data Model: `StatusResponse`

Generic status response.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | string | ✓ |  |
| `status` | string | ✓ |  |

---

### Data Model: `SubmitInputRequest`

Request body for submitting input.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `config` | object |  | Plugin-specific configuration |
| `plugin_key` | string |  | Key of the input plugin to use |
| `raw_data` | object |  | Additional raw input data |
| `topic` | string |  | The debate topic / case description |

---

### Data Model: `SubmitInputResponse`

Response after submitting input.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `job_id` | string | ✓ |  |
| `plugin_key` | string | ✓ |  |
| `status` | string | ✓ |  |

---

### Data Model: `TemplatePlaceholder`

Defines a single placeholder within a WorkflowTemplate.

Placeholders are replaced with concrete values during instantiation.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `default` | string |  |  |
| `description` | string |  |  |
| `key` | string | ✓ |  |
| `type` | enum(string, blueprint_ref, integer, float) |  |  |

---

### Data Model: `TerminationCondition`

A condition that determines when a workflow should stop.

Examples:
- ``max_rounds``: stop after N rounds
- ``consensus_reached``: stop when consensus threshold is met
- ``time_limit``: stop after N seconds

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `description` | string |  |  |
| `type` | enum(max_rounds, consensus_reached, time_limit, custom) |  |  |
| `value` | string |  |  |

---

### Data Model: `ToneProfile`

Debate tone/style configuration for agent nodes.

Defines how an agent should communicate: formal vs. casual,
heated vs. neutral, verbose vs. concise, etc.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `created_at` | string |  |  |
| `custom_instructions` | string |  |  |
| `description` | string |  |  |
| `emotional_valence` | number |  |  |
| `formality` | number |  |  |
| `id` | string |  |  |
| `is_system` | boolean |  |  |
| `name` | string | ✓ |  |
| `rhetorical_mode` | enum(none, questioning, assertive, dialectic) |  |  |
| `style` | enum(heated, academic, conversational, socratic, neutral) |  |  |
| `updated_at` | string |  |  |
| `verbosity` | enum(concise, normal, verbose) |  |  |

---

### Data Model: `TranslatePromptRequest`

Request body for translating a prompt variant.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `auto_approve` | boolean |  | Auto-approve if quality meets threshold |
| `force` | boolean |  | Force re-translation |
| `target_language` | string | ✓ | Target language code (e.g. 'de') |

---

### Data Model: `TranslationSetRequest`

Set a single UI translation.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `key` | string | ✓ |  |
| `namespace` | string |  |  |
| `value` | string | ✓ |  |

---

### Data Model: `UninstallRequest`

Request body for module uninstallation.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `force` | boolean |  | Force uninstall ignoring dependencies |

---

### Data Model: `UtilityLLMRequest`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `profile_id` | string | ✓ |  |

---

### Data Model: `ValidateRequest`

Request body for module validation.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `manifest` | object | ✓ | Module manifest dict |

---

### Data Model: `ValidationError`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ctx` | object |  |  |
| `input` | string |  |  |
| `loc` | array[any] | ✓ |  |
| `msg` | string | ✓ |  |
| `type` | string | ✓ |  |

---

### Data Model: `WorkflowDefinition`

Defines a complete debate workflow.

References AgentBlueprints from the catalog by ID.
Does NOT duplicate blueprint data.

The ``nodes`` and ``edges`` fields provide the structured graph
representation.  ``execution_order``, ``conditional_edges``, and
``interjection_points`` are retained for backward compatibility with
the list-based representation.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `canvas_layout_id` | string |  |  |
| `conditional_edges` | array[[ConditionalEdge](#data-model-conditionaledge)] |  |  |
| `created_at` | string |  |  |
| `description` | string |  |  |
| `edges` | array[[WorkflowEdge](#data-model-workflowedge)] |  |  |
| `entry_point` | string |  |  |
| `execution_order` | array[string] |  |  |
| `id` | string |  |  |
| `input_config` | string |  | Input Composer configuration for this workflow. Keys: default_input_plugin, stt_profile_id, a2a_inbound_enabled |
| `interjection_points` | array[[InterjectionPoint](#data-model-interjectionpoint)] |  |  |
| `is_active` | boolean |  |  |
| `is_locked` | boolean |  |  |
| `name` | string | ✓ |  |
| `node_blueprint_map` | object |  |  |
| `nodes` | array[[WorkflowNode](#data-model-workflownode)] |  |  |
| `tags` | array[string] |  |  |
| `template_id` | string |  |  |
| `termination_conditions` | array[[TerminationCondition](#data-model-terminationcondition)] |  |  |
| `updated_at` | string |  |  |
| `version` | integer |  |  |

---

### Data Model: `WorkflowEdge`

An edge connecting two workflow nodes.

Edge types:
- ``sequential``: unconditional forward connection
- ``conditional``: branching based on a condition expression
- ``interjection``: connects to an interjection point
- ``feedback``: loop-back edge (e.g. moderator → strategist for another round)
- ``injects_config``: config injection from tone_profile node to agent node

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `condition` | string |  |  |
| `id` | string |  |  |
| `label` | string |  |  |
| `source` | string | ✓ |  |
| `target` | string | ✓ |  |
| `type` | enum(sequential, conditional, interjection, feedback, injects_config) |  |  |

---

### Data Model: `WorkflowNode`

A single node in a workflow graph.

Each node has a type that determines its behavior during execution.
Agent-type nodes (strategist, critic, optimizer, moderator) must
reference an AgentBlueprint via ``agent_blueprint_id``.
The generic ``wf-agent`` type references an ``AgentBundle`` via
``bundle_id`` instead.
Tone-profile nodes reference a ToneProfile from the catalog or
define an inline profile.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agent_blueprint_id` | string |  |  |
| `bundle_id` | string |  |  |
| `config` | object |  |  |
| `id` | string | ✓ |  |
| `label` | string |  |  |
| `position` | object |  |  |
| `type` | enum(wf-input, wf-initialize, wf-strategist, wf-critic, wf-fact-checker, wf-optimizer, wf-moderator, wf-analyst, wf-creative, wf-user-injection, wf-gate, wf-tone-profile, wf-agent) | ✓ |  |

---

### Data Model: `WorkflowTemplate`

A reusable workflow template with placeholder substitution.

Templates contain a ``template_data`` dictionary that mirrors the
structure of a ``WorkflowDefinition`` (nodes, edges, entry_point,
termination_conditions) but may contain ``{{key}}`` placeholders in
string fields.

During instantiation, all placeholders are replaced with concrete
values provided by the user, and the result is validated as a
``WorkflowDefinition``.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `category` | enum(system, custom) |  |  |
| `created_at` | string |  |  |
| `description` | string |  |  |
| `id` | string | ✓ |  |
| `is_system` | boolean |  |  |
| `name` | string | ✓ |  |
| `placeholders` | array[[TemplatePlaceholder](#data-model-templateplaceholder)] |  |  |
| `source_workflow_id` | string |  |  |
| `tags` | array[string] |  |  |
| `template_data` | object |  |  |
| `updated_at` | string |  |  |

---

### Data Model: `backend__api__routers__modules__TranslateRequest`

Request body for module translation.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `force` | boolean |  | Force re-translation |
| `target_language` | string | ✓ | Target language code (e.g. 'de') |

---

### Data Model: `backend__api__routers__translation__TranslateRequest`

Request body for module translation.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `auto_approve` | boolean |  | Auto-approve translations meeting quality threshold |
| `force` | boolean |  | Force re-translation even if cached |
| `llm_profile_id` | string |  | Override LLM profile for translation |
| `quality_threshold` | number |  | Minimum quality score for auto-approval (0.0-1.0) |
| `skip_back_translation` | boolean |  | Skip back-translation QA (faster but lower quality) |
| `target_language` | string | ✓ | Target language code (e.g. 'de') |

---
