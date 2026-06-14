/**
 * New-debate flow — pure logic for the Case-Space New-Debate form.
 *
 * Extracted from `components/case-space/NewDebateForm.svelte` so the
 * branching between "existing case", "new case", and the
 * tag-suggestion rule can be unit-tested in isolation, without
 * mounting a Svelte component.
 *
 * Phase 3.7 of plans/2026-06-14_case-space-impl-todos.md.
 *
 * The functions are pure (no DOM, no fetch) so they can be reused
 * server-side or in CLI scripts in the future, and they can be
 * tested without the heavy @testing-library/svelte machinery.
 *
 * @see plans/2026-06-14_case-space-impl-todos.md (Phase 3.7)
 */

/**
 * Resolve the initial mode of the New-Debate form.
 *
 * - 'existing' when there is an active case (one-click happy path)
 * - 'new'      when no active case is selected (first-debate path)
 *
 * 3.7.1 — Default = active case.
 */
export function resolveInitialMode(activeCaseId) {
  return activeCaseId ? 'existing' : 'new';
}

/**
 * Pick the top-N tag suggestions from a case.
 *
 * Tolerates the case object using either `tags` (string[]) or
 * `tag_ids` (string[]) and either length — the actual `tag` objects
 * (with `tag_id` and `name`) are filtered in a second pass.
 *
 * 3.7.3 — Top-3 of the active case are surfaced as quick-buttons.
 */
export function pickTopTagIds(caseObj, allTags, limit = 3) {
  if (!caseObj) return [];
  const ids = caseObj.tag_ids || caseObj.tags || [];
  if (!Array.isArray(ids) || !Array.isArray(allTags)) return [];
  const map = new Map(allTags.map((t) => [t.tag_id, t]));
  return ids
    .map((id) => map.get(id))
    .filter(Boolean)
    .slice(0, limit);
}

/**
 * Determine whether the tag-suggestion strip should still be shown.
 *
 * The strip hides as soon as the user picks tags via the picker OR
 * starts typing a case name — both express intent.  The caller
 * supplies the current local state.
 */
export function shouldShowTagSuggestions({
  dismissed,
  loaded,
  suggestions,
  pickedTagCount,
  hasTitle,
}) {
  if (dismissed) return false;
  if (!loaded) return false;
  if (!Array.isArray(suggestions) || suggestions.length === 0) return false;
  if (pickedTagCount > 0) return false;
  if (hasTitle) return false;
  return true;
}

/**
 * Apply a suggested tag to the current selection (idempotent).
 */
export function applySuggestion(currentTagIds, tag) {
  if (!tag) return currentTagIds;
  if (currentTagIds.includes(tag.tag_id)) return currentTagIds;
  return [...currentTagIds, tag.tag_id];
}

/**
 * Validate the New-Debate form before submitting.
 *
 * Returns null when valid, or a string error key/message otherwise.
 * The error string follows the i18n namespace used in the component
 * (`caseSpace.newDebate.*`) so callers can resolve it via t() and
 * also see the raw key in tests.
 */
export function validateNewDebateForm({
  topic,
  mode,
  selectedCaseId,
  activeCaseId,
  newCaseTitle,
}) {
  if (!(topic || '').trim()) {
    return 'topicRequired';
  }
  if (mode === 'new') {
    if (!(newCaseTitle || '').trim()) {
      return 'caseTitleRequired';
    }
  } else {
    if (!selectedCaseId && !activeCaseId) {
      return 'caseRequired';
    }
  }
  return null;
}

/**
 * Compute the final `caseId` that should receive the new debate.
 *
 * - 'new'  → returns null (the caller must await the createCase call)
 * - 'existing' → prefers `selectedCaseId`, falls back to `activeCaseId`
 */
export function resolveTargetCaseId({ mode, selectedCaseId, activeCaseId }) {
  if (mode === 'new') return null;
  return selectedCaseId || activeCaseId || null;
}
