/**
 * Unit Tests — New-Debate flow (Case-Space Phase 3.7)
 *
 * Validates the pure logic extracted from
 * `components/case-space/NewDebateForm.svelte` into
 * `lib/stores/newDebateFlow.svelte.js`.
 *
 * Tested behaviours:
 * - 3.7.1  Initial mode = 'existing' iff active case is set
 * - 3.7.2  Mode 'new' works in the validate/resolve path
 * - 3.7.3  Top-N tag suggestions resolve from the active case and
 *          hide when the user picks tags or types a title
 *
 * @see plans/2026-06-14_case-space-impl-todos.md (Phase 3.7)
 */

import { describe, it, expect } from 'vitest';
import {
  resolveInitialMode,
  pickTopTagIds,
  shouldShowTagSuggestions,
  applySuggestion,
  validateNewDebateForm,
  resolveTargetCaseId,
} from '../../src/lib/stores/newDebateFlow.svelte.js';

// ─── 3.7.1 — Initial mode ─────────────────────────────────────────
describe('resolveInitialMode (3.7.1)', () => {
  it('returns "existing" when an active case id is present', () => {
    expect(resolveInitialMode('case-123')).toBe('existing');
  });
  it('returns "new" when no active case is selected', () => {
    expect(resolveInitialMode(null)).toBe('new');
    expect(resolveInitialMode(undefined)).toBe('new');
    expect(resolveInitialMode('')).toBe('new');
  });
});

// ─── 3.7.3 — Tag suggestions ──────────────────────────────────────
describe('pickTopTagIds (3.7.3)', () => {
  const allTags = [
    { tag_id: 't1', name: 'ethics', color: '#abc' },
    { tag_id: 't2', name: 'research', color: '#def' },
    { tag_id: 't3', name: 'urgent', color: '#fed' },
    { tag_id: 't4', name: 'q3', color: '#bbb' },
  ];

  it('returns the top-N tag objects of the active case', () => {
    const c = { tag_ids: ['t1', 't3', 't2', 't4'] };
    expect(pickTopTagIds(c, allTags, 3)).toEqual([
      { tag_id: 't1', name: 'ethics', color: '#abc' },
      { tag_id: 't3', name: 'urgent', color: '#fed' },
      { tag_id: 't2', name: 'research', color: '#def' },
    ]);
  });

  it('accepts the "tags" string[] field as a fallback', () => {
    const c = { tags: ['t1'] };
    expect(pickTopTagIds(c, allTags, 3)).toEqual([
      { tag_id: 't1', name: 'ethics', color: '#abc' },
    ]);
  });

  it('skips unknown tag ids gracefully', () => {
    const c = { tag_ids: ['missing', 't1'] };
    expect(pickTopTagIds(c, allTags, 3)).toEqual([
      { tag_id: 't1', name: 'ethics', color: '#abc' },
    ]);
  });

  it('returns [] when the case has no tags', () => {
    expect(pickTopTagIds({}, allTags, 3)).toEqual([]);
    expect(pickTopTagIds({ tag_ids: [] }, allTags, 3)).toEqual([]);
  });

  it('returns [] when allTags is missing or not an array', () => {
    expect(pickTopTagIds({ tag_ids: ['t1'] }, null, 3)).toEqual([]);
    expect(pickTopTagIds({ tag_ids: ['t1'] }, undefined, 3)).toEqual([]);
  });

  it('returns [] when the case object is null', () => {
    expect(pickTopTagIds(null, allTags, 3)).toEqual([]);
  });
});

describe('shouldShowTagSuggestions (3.7.3)', () => {
  const base = {
    dismissed: false,
    loaded: true,
    suggestions: [{ tag_id: 't1', name: 'ethics' }],
    pickedTagCount: 0,
    hasTitle: false,
  };

  it('shows by default', () => {
    expect(shouldShowTagSuggestions(base)).toBe(true);
  });

  it('hides when the user dismissed it', () => {
    expect(shouldShowTagSuggestions({ ...base, dismissed: true })).toBe(false);
  });

  it('hides before suggestions have loaded', () => {
    expect(shouldShowTagSuggestions({ ...base, loaded: false })).toBe(false);
  });

  it('hides when there are no suggestions', () => {
    expect(shouldShowTagSuggestions({ ...base, suggestions: [] })).toBe(false);
  });

  it('hides as soon as the user picks a tag', () => {
    expect(shouldShowTagSuggestions({ ...base, pickedTagCount: 1 })).toBe(false);
  });

  it('hides as soon as the user starts typing a case name', () => {
    expect(shouldShowTagSuggestions({ ...base, hasTitle: true })).toBe(false);
  });
});

describe('applySuggestion', () => {
  const tag = { tag_id: 't1', name: 'ethics' };

  it('appends a new tag id', () => {
    expect(applySuggestion([], tag)).toEqual(['t1']);
    expect(applySuggestion(['t2'], tag)).toEqual(['t2', 't1']);
  });

  it('is idempotent — does not duplicate an already-picked tag', () => {
    expect(applySuggestion(['t1'], tag)).toEqual(['t1']);
  });

  it('returns the input unchanged when the tag is null/undefined', () => {
    expect(applySuggestion(['t1'], null)).toEqual(['t1']);
    expect(applySuggestion(['t1'], undefined)).toEqual(['t1']);
  });
});

// ─── Validation ───────────────────────────────────────────────────
describe('validateNewDebateForm', () => {
  const okExisting = {
    topic: 'Teaching AI human values',
    mode: 'existing',
    selectedCaseId: 'case-1',
    activeCaseId: null,
    newCaseTitle: '',
  };
  const okNew = {
    topic: 'Teaching AI human values',
    mode: 'new',
    selectedCaseId: null,
    activeCaseId: null,
    newCaseTitle: 'AI Ethics Research',
  };
  const okExistingActiveFallback = {
    topic: 'Topic',
    mode: 'existing',
    selectedCaseId: null,
    activeCaseId: 'case-2',
    newCaseTitle: '',
  };

  it('accepts a valid existing-case form', () => {
    expect(validateNewDebateForm(okExisting)).toBeNull();
  });

  it('accepts a valid new-case form', () => {
    expect(validateNewDebateForm(okNew)).toBeNull();
  });

  it('accepts an existing-case form with the active-case fallback', () => {
    expect(validateNewDebateForm(okExistingActiveFallback)).toBeNull();
  });

  it('rejects an empty topic', () => {
    expect(
      validateNewDebateForm({ ...okExisting, topic: '   ' })
    ).toBe('topicRequired');
  });

  it('rejects a new case without a title', () => {
    expect(
      validateNewDebateForm({ ...okNew, newCaseTitle: '' })
    ).toBe('caseTitleRequired');
    expect(
      validateNewDebateForm({ ...okNew, newCaseTitle: '   ' })
    ).toBe('caseTitleRequired');
  });

  it('rejects an existing-case form without any case source', () => {
    expect(
      validateNewDebateForm({
        topic: 'Topic',
        mode: 'existing',
        selectedCaseId: null,
        activeCaseId: null,
        newCaseTitle: '',
      })
    ).toBe('caseRequired');
  });
});

// ─── resolveTargetCaseId ──────────────────────────────────────────
describe('resolveTargetCaseId', () => {
  it('returns null in "new" mode (caller must await createCase)', () => {
    expect(
      resolveTargetCaseId({ mode: 'new', selectedCaseId: null, activeCaseId: 'case-1' })
    ).toBeNull();
  });

  it('prefers selectedCaseId over activeCaseId', () => {
    expect(
      resolveTargetCaseId({
        mode: 'existing',
        selectedCaseId: 'case-2',
        activeCaseId: 'case-1',
      })
    ).toBe('case-2');
  });

  it('falls back to activeCaseId when no explicit selection', () => {
    expect(
      resolveTargetCaseId({
        mode: 'existing',
        selectedCaseId: null,
        activeCaseId: 'case-1',
      })
    ).toBe('case-1');
  });

  it('returns null when nothing is available', () => {
    expect(
      resolveTargetCaseId({ mode: 'existing', selectedCaseId: null, activeCaseId: null })
    ).toBeNull();
  });
});
