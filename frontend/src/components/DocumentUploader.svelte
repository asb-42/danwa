<script>
  import { tStore } from '../lib/i18n/index.js';
  import { uploadDocument } from '../lib/api.js';
  import { addToast } from '../lib/stores.js';
  import { currentTenant } from '../lib/stores/auth.svelte.js';
  import { activeCase, setActiveCase } from '../lib/stores.js';
  import { getCases } from '../lib/api/case.js';

  /**
   * Case-Space Phase 3.8 — the uploader now has a case selector.
   * The user must explicitly choose a case (or "no case — in Inbox")
   * before files can be dropped in.  The chosen case is written
   * back to activeCase so subsequent uploads inherit it.
   */
  let { onUpload = null, compact = false } = $props();

  let dragOver = $state(false);
  let uploading = $state(false);
  let fileInput = $state(null);

  // Phase 3.8 — case selector state
  let caseOptions = $state([]);
  let casesLoading = $state(false);
  let caseOptionsLoaded = $state(false);
  let chosenCaseId = $state(null);  // null = "no case, land in Inbox"

  let t = $derived($tStore);
  let tenantId = $derived($currentTenant?.id);
  let activeCaseId = $derived($activeCase?.id);

  // Initialise the case selector: if there is already an active
  // case, pre-select it.  Otherwise the user must pick.
  $effect(() => {
    if (activeCaseId && !chosenCaseId) chosenCaseId = activeCaseId;
  });

  // Lazy-load available cases for the selector.
  $effect(() => {
    if (tenantId && !casesLoading && !caseOptionsLoaded) {
      casesLoading = true;
      getCases(tenantId)
        .then((list) => {
          caseOptions = Array.isArray(list) ? list : [];
          caseOptionsLoaded = true;
        })
        .catch(() => {
          caseOptions = [];
          caseOptionsLoaded = true;
        })
        .finally(() => {
          casesLoading = false;
        });
    }
  });

  function pickCase(id) {
    chosenCaseId = id;
    if (id) setActiveCase(id);  // sync to global so X-Case-Id header follows
  }

  // Phase 3.8 — guard.  Uploads are only allowed once a case is
  // selected (or the user explicitly chose "no case / Inbox").
  let canUpload = $derived(chosenCaseId !== undefined);

  async function handleUpload(files) {
    if (!files || files.length === 0) return;
    if (!canUpload) {
      addToast({
        type: 'warning',
        message: t?.caseSpace?.newDebate?.caseRequired ??
          'Please pick a case (or "No case" for the Inbox) before uploading.',
      });
      return;
    }
    uploading = true;
    try {
      const results = [];
      for (const file of files) {
        const result = await uploadDocument(file);
        results.push(result);
      }
      if (onUpload) onUpload(results);
    } catch (e) {
      addToast({ type: 'error', message: t('documents.uploadFailed', { error: e.message }) });
    } finally {
      uploading = false;
    }
  }

  function handleDrop(event) {
    event.preventDefault();
    dragOver = false;
    handleUpload(event.dataTransfer.files);
  }

  function handleDragOver(event) {
    event.preventDefault();
    dragOver = true;
  }

  function handleDragLeave() {
    dragOver = false;
  }

  function handleFileSelect(event) {
    handleUpload(event.target.files);
    if (fileInput) fileInput.value = '';
  }
</script>

{#if !compact}
  <!-- Phase 3.8 — Case selector (Pflicht) -->
  <div
    class="mb-3 p-3 border rounded-md
           bg-white dark:bg-gray-800
           border-gray-200 dark:border-gray-700
           text-gray-900 dark:text-gray-100"
    data-testid="case-selector"
  >
    <label
      for="upload-case"
      class="block text-xs font-medium mb-1
             text-gray-700 dark:text-gray-300"
    >
      {t?.caseSpace?.newDebate?.caseLabel ?? 'Case'}
      <span class="text-red-500">*</span>
    </label>
    {#if casesLoading}
      <p class="text-sm text-gray-500 dark:text-gray-400">
        {t?.common?.loading ?? 'Loading cases…'}
      </p>
    {:else}
      <select
        id="upload-case"
        value={chosenCaseId || ''}
        onchange={(e) => pickCase(e.target.value || null)}
        class="w-full px-2 py-1.5 border rounded text-sm
               border-gray-300 dark:border-gray-600
               bg-white dark:bg-gray-700
               text-gray-900 dark:text-gray-100
               focus:outline-none focus:ring-2 focus:ring-blue-500"
        data-testid="upload-case-select"
      >
        <option value="">
          {t?.caseSpace?.workspace?.noCases ?? '— No case (land in Inbox) —'}
        </option>
        {#each caseOptions as c (c.id)}
          <option value={c.id}>{c.title || c.id}</option>
        {/each}
      </select>
      <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
        {chosenCaseId
          ? (t?.caseSpace?.workspace?.caseAttached ??
             'Files will be attached to the selected case.')
          : (t?.caseSpace?.workspace?.caseInboxHint ??
             'Files uploaded without a case appear in the Inbox for later sorting.')}
      </p>
    {/if}
  </div>
{/if}

<div
  class="border-2 border-dashed rounded-lg text-center transition-colors cursor-pointer
    {compact ? 'p-4' : 'p-8'}
    {dragOver
      ? 'border-blue-400 bg-blue-50 dark:bg-blue-900/20'
      : 'border-gray-300 dark:border-gray-600 hover:border-blue-300 dark:hover:border-blue-600'}
    {!canUpload ? 'opacity-50 cursor-not-allowed' : ''}"
  ondrop={handleDrop}
  ondragover={handleDragOver}
  ondragleave={handleDragLeave}
  onclick={() => canUpload && fileInput?.click()}
  role="region"
  aria-label={t('documents.upload')}
  tabindex="0"
  onkeydown={(e) => e.key === 'Enter' && canUpload && fileInput?.click()}
>
  <input
    bind:this={fileInput}
    type="file"
    multiple
    accept=".pdf,.docx,.odt,.txt,.md,.png,.jpg,.jpeg,.gif,.bmp,.tiff"
    class="hidden"
    onchange={handleFileSelect}
  />
  <div class="space-y-1">
    <p class="text-{compact ? '2xl' : '4xl'}">📄</p>
    <p class="text-gray-600 dark:text-gray-300 font-medium text-{compact ? 'xs' : 'sm'}">
      {uploading ? t('documents.uploading') : t('documents.dragDrop')}
    </p>
    {#if !compact}
      <p class="text-xs text-gray-500 dark:text-gray-400">
        {t('documents.supportedFormats')}
      </p>
    {/if}
  </div>
</div>
