<!--
  WelcomeCard — first-time-user onboarding card.

  Renders only when the tenant has no cases (the strongest
  signal that the user is new).  Three clickable paths:

    1. Create your first Case
    2. Upload reference documents (optional)
    3. Start your first debate

  All three are non-modal: the user can dismiss the card and
  navigate to any other view via the sidebar; the card only
  reappears on the dashboard if they have not created any
  case yet.

  @see plans/2026-06-14_case-space-workspace.md (Phase 3.3)
-->
<script>
  import { tStore } from '../../lib/i18n/index.js';
  import { getOnboardingState } from '../../lib/api/onboarding.js';
  import { currentTenant } from '../../lib/stores/auth.svelte.js';

  let { navigate = () => {} } = $props();

  let t = $derived($tStore);
  let tenantId = $derived($currentTenant?.id);

  let dismissed = $state(false);
  let state = $state({ has_cases: false, has_documents: false, has_debates: false });
  let loading = $state(true);

  // Reload whenever the tenant changes
  $effect(() => {
    if (!tenantId) {
      state = { has_cases: false, has_documents: false, has_debates: false };
      loading = false;
      return;
    }
    loading = true;
    getOnboardingState(tenantId).then((s) => {
      state = s;
      loading = false;
    });
  });

  // Show the card only when:
  //  - not dismissed
  //  - we have a tenant
  //  - that tenant has no cases
  let visible = $derived(!dismissed && !!tenantId && !loading && !state.has_cases);
</script>

{#if visible}
  <section class="welcome-card" role="region" aria-label="Welcome to Danwa">
    <header class="welcome-header">
      <h2>{t?.caseSpace?.onboarding?.title ?? 'Welcome to Danwa'}</h2>
      <button
        class="btn-link"
        type="button"
        onclick={() => (dismissed = true)}
        aria-label={t?.caseSpace?.onboarding?.dismissAriaLabel ?? 'Dismiss welcome card'}
      >
        {t?.caseSpace?.onboarding?.dismiss ?? 'Dismiss'}
      </button>
    </header>

    <p class="welcome-intro">
      {t?.caseSpace?.onboarding?.intro ??
        'To get started, create your first Case. You can do these in any order — the Inbox will keep track.'}
    </p>

    <ol class="welcome-steps">
      <li class="step">
        <span class="step-num">1</span>
        <div class="step-body">
          <strong>{t?.caseSpace?.onboarding?.step1Title ?? 'Create your first Case'}</strong>
          <p>{t?.caseSpace?.onboarding?.step1Body ?? 'Cases group related debates and documents.'}</p>
          {#if navigate}
            <button class="btn btn-primary" type="button" onclick={() => navigate('case-list')}>
              {t?.caseSpace?.onboarding?.step1Action ?? 'Create Case'}
            </button>
          {/if}
        </div>
      </li>
      <li class="step">
        <span class="step-num">2</span>
        <div class="step-body">
          <strong>{t?.caseSpace?.onboarding?.step2Title ?? 'Upload reference documents (optional)'}</strong>
          <p>{t?.caseSpace?.onboarding?.step2Body ?? 'PDFs, DOCX, TXT — they will be searchable via RAG.'}</p>
          {#if navigate}
            <button class="btn" type="button" onclick={() => navigate('documents')}>
              {t?.caseSpace?.onboarding?.step2Action ?? 'Upload Documents'}
            </button>
          {/if}
        </div>
      </li>
      <li class="step">
        <span class="step-num">3</span>
        <div class="step-body">
          <strong>{t?.caseSpace?.onboarding?.step3Title ?? 'Start your first debate'}</strong>
          <p>{t?.caseSpace?.onboarding?.step3Body ?? 'Combine agents to explore a question in depth.'}</p>
          {#if navigate}
            <button class="btn" type="button" onclick={() => navigate('mvp-debate')}>
              {t?.caseSpace?.onboarding?.step3Action ?? 'Start Debate'}
            </button>
          {/if}
        </div>
      </li>
    </ol>
  </section>
{/if}

<style>
  .welcome-card {
    background: var(--color-bg-elevated, #fff);
    border: 1px solid var(--color-border, #e5e7eb);
    border-radius: 12px;
    padding: 1.5rem 1.75rem;
    margin: 1.5rem auto;
    max-width: 800px;
  }
  .welcome-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.5rem;
  }
  .welcome-header h2 {
    margin: 0;
    font-size: 1.4rem;
  }
  .welcome-intro {
    margin: 0 0 1rem;
    color: var(--color-text-muted, #666);
  }
  .welcome-steps {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    gap: 0.75rem;
  }
  .step {
    display: flex;
    align-items: flex-start;
    gap: 1rem;
    padding: 0.75rem;
    border: 1px solid var(--color-border, #e5e7eb);
    border-radius: 8px;
    background: var(--color-bg, #fafafa);
  }
  .step-num {
    flex-shrink: 0;
    width: 2rem;
    height: 2rem;
    border-radius: 50%;
    background: var(--color-primary, #3b82f6);
    color: white;
    font-weight: 600;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .step-body { flex: 1; }
  .step-body p {
    margin: 0.25rem 0 0.5rem;
    color: var(--color-text-muted, #666);
    font-size: 0.9rem;
  }
  .btn {
    padding: 0.4rem 0.85rem;
    border: 1px solid var(--color-border, #ddd);
    background: var(--color-bg-elevated, #fff);
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.9rem;
  }
  .btn-primary {
    background: var(--color-primary, #3b82f6);
    color: white;
    border-color: transparent;
  }
  .btn-link {
    background: transparent;
    border: none;
    color: var(--color-text-muted, #666);
    cursor: pointer;
    font-size: 0.9rem;
  }
  .btn-link:hover { color: var(--color-text, #222); }
</style>
