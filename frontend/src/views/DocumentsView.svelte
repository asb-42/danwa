<script>
  import { onMount } from 'svelte';
  import { i18n } from '../lib/i18n/index.js';
  import { activeProject } from '../lib/stores.js';
  import { getDocuments, getDocument, uploadDocument, deleteDocument, moveDocument, addDocumentToRAG, removeDocumentFromRAG, searchRAG, getOcrStatus, getProjects } from '../lib/api.js';

  let { navigate } = $props();

  let documents = $state([]);
  let loading = $state(true);
  let uploading = $state(false);
  let error = $state('');
  let dragOver = $state(false);
  let fileInput;

  // Document viewer state
  let viewingDoc = $state(null);
  let viewingDocContent = $state(null);
  let viewingLoading = $state(false);

  // RAG search state
  let searchQuery = $state('');
  let searchLimit = $state(5);
  let searchResults = $state(null);
  let isSearching = $state(false);
  let searchError = $state('');

  // OCR availability state
  let ocrAvailable = $state(null); // null = loading, true/false = loaded

  async function handleRAGSearch() {
    if (!searchQuery.trim()) return;
    isSearching = true;
    searchError = '';
    searchResults = null;
    try {
      searchResults = await searchRAG(searchQuery.trim(), searchLimit);
    } catch (e) {
      searchError = e.message;
    } finally {
      isSearching = false;
    }
  }

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

  let projectId = $derived($activeProject?.id);

  async function loadDocuments() {
    if (!projectId) {
      documents = [];
      loading = false;
      return;
    }
    loading = true;
    error = '';
    try {
      documents = await getDocuments();
    } catch (e) {
      error = e.message;
      documents = [];
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    loadDocuments();
    // Check OCR availability (non-blocking)
    getOcrStatus()
      .then((res) => { ocrAvailable = res.available; })
      .catch(() => { ocrAvailable = false; });
  });

  // Reload when project changes
  $effect(() => {
    if (projectId) {
      loadDocuments();
    }
  });

  let uploadResults = $state([]);

  async function handleUpload(files) {
    if (!files || files.length === 0) return;
    uploading = true;
    error = '';
    uploadResults = [];
    try {
      for (const file of files) {
        const ext = file.name.split('.').pop().toLowerCase();
        const isImage = ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'webp'].includes(ext);

        uploadResults = [...uploadResults, {
          filename: file.name,
          status: 'uploading',
          message: isImage ? `${file.name} — Upload läuft…` : `${file.name} — Upload läuft…`,
        }];

        let res;
        try {
          res = await uploadDocument(file);
        } catch (e) {
          uploadResults = uploadResults.map(r =>
            r.filename === file.name ? { ...r, status: 'error', message: `${file.name} — ${e.message}` } : r
          );
          continue;
        }

        if (res.ocr_used) {
          const engine = res.ocr_engine === 'tesseract' ? 'Tesseract' : res.ocr_engine || 'OCR';
          uploadResults = uploadResults.map(r =>
            r.filename === file.name
              ? {
                  ...r,
                  status: 'success',
                  message: `${file.name} — ${engine}: ${res.char_count} Zeichen, ${res.word_count} Wörter, ${res.chunk_count} Chunks`,
                }
              : r
          );
        } else if (isImage) {
          uploadResults = uploadResults.map(r =>
            r.filename === file.name
              ? { ...r, status: 'warning', message: `${file.name} — Keine Texterkennung (OCR nicht verfügbar), ${res.chunk_count} Chunks` }
              : r
          );
        } else {
          uploadResults = uploadResults.map(r =>
            r.filename === file.name
              ? { ...r, status: 'success', message: `${file.name} — ${res.char_count} Zeichen, ${res.word_count} Wörter, ${res.chunk_count} Chunks` }
              : r
          );
        }
      }
      await loadDocuments();
    } catch (e) {
      error = e.message || t('documents.uploadError');
    } finally {
      uploading = false;
    }
  }

  function handleFileSelect(event) {
    handleUpload(event.target.files);
    if (fileInput) fileInput.value = '';
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

  async function handleDelete(doc) {
    if (!confirm(t('documents.deleteConfirm'))) return;
    try {
      await deleteDocument(doc.id);
      documents = documents.filter(d => d.id !== doc.id);
    } catch (e) {
      error = e.message;
    }
  }

  async function toggleRAG(doc) {
    try {
      if (doc.in_rag) {
        await removeDocumentFromRAG(doc.id);
      } else {
        await addDocumentToRAG(doc.id);
      }
      // Update local state
      documents = documents.map(d =>
        d.id === doc.id ? { ...d, in_rag: !d.in_rag } : d
      );
    } catch (e) {
      error = e.message;
    }
  }

  // Move document state
  let moveDialogOpen = $state(false);
  let moveDoc = $state(null);
  let moveProjects = $state([]);
  let moveTargetId = $state('');
  let moveSaving = $state(false);
  let moveError = $state('');

  async function openMoveDialog(doc) {
    moveDoc = doc;
    moveTargetId = '';
    moveError = '';
    moveSaving = false;
    try {
      const allProjects = await getProjects();
      moveProjects = allProjects.filter(p => p.id !== projectId);
    } catch (e) {
      moveError = 'Failed to load projects';
    }
    moveDialogOpen = true;
  }

  async function confirmMove() {
    if (!moveTargetId || !moveDoc) return;
    moveSaving = true;
    moveError = '';
    try {
      await moveDocument(moveDoc.id, moveTargetId);
      documents = documents.filter(d => d.id !== moveDoc.id);
      moveDialogOpen = false;
      moveDoc = null;
    } catch (e) {
      moveError = e.message;
    } finally {
      moveSaving = false;
    }
  }

  function closeMoveDialog() {
    moveDialogOpen = false;
    moveDoc = null;
  }

  async function viewDocument(doc) {
    viewingDoc = doc;
    viewingLoading = true;
    viewingDocContent = null;
    try {
      viewingDocContent = await getDocument(doc.id);
    } catch (e) {
      error = e.message;
      viewingDoc = null;
    } finally {
      viewingLoading = false;
    }
  }

  function closeViewer() {
    viewingDoc = null;
    viewingDocContent = null;
  }

  function formatDate(dateStr) {
    if (!dateStr) return '—';
    try {
      return new Date(dateStr).toLocaleString();
    } catch {
      return dateStr;
    }
  }

  function formatFileSize(bytes) {
    if (!bytes || bytes === 0) return '—';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function getFileIcon(filename) {
    if (!filename) return '📄';
    const ext = filename.split('.').pop().toLowerCase();
    const icons = {
      pdf: '📕', doc: '📘', docx: '📘', odt: '📘',
      txt: '📝', md: '📝',
      png: '🖼️', jpg: '🖼️', jpeg: '🖼️', gif: '🖼️', bmp: '🖼️', tiff: '🖼️',
      csv: '📊', xls: '📊', xlsx: '📊',
    };
    return icons[ext] || '📄';
  }
</script>

<div class="w-full p-6 space-y-6">
  <div class="flex items-center justify-between">
    <h1 class="text-2xl font-bold text-gray-800 dark:text-white">
      {t('documents.title')}
    </h1>
  </div>

  {#if error}
    <div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-300" role="alert">
      {error}
    </div>
  {/if}
  {#each uploadResults as r}
    <!-- svelte-ignore a11y_no_redundant_roles -->
    <div
      class="rounded-lg px-4 py-3 text-sm flex items-center gap-2 {r.status === 'success' ? 'bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 text-green-700 dark:text-green-300' : r.status === 'warning' ? 'bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-800 text-orange-700 dark:text-orange-300' : r.status === 'error' ? 'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300' : 'bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 text-blue-700 dark:text-blue-300'}"
      role="status"
    >
      {#if r.status === 'uploading'}
        <span class="w-3 h-3 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></span>
      {:else if r.status === 'success'}
        <span>✅</span>
      {:else if r.status === 'warning'}
        <span>⚠️</span>
      {:else}
        <span>❌</span>
      {/if}
      <span>{r.message}</span>
    </div>
  {/each}

  <!-- Upload area -->
  <div
    class="border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer
      {dragOver
        ? 'border-blue-400 bg-blue-50 dark:bg-blue-900/20'
        : 'border-gray-300 dark:border-gray-600 hover:border-blue-300 dark:hover:border-blue-600'}"
    ondrop={handleDrop}
    ondragover={handleDragOver}
    ondragleave={handleDragLeave}
    onclick={() => fileInput?.click()}
    role="button"
    aria-label={t('documents.upload')}
    tabindex="0"
    onkeydown={(e) => e.key === 'Enter' && fileInput?.click()}
  >
    <input
      bind:this={fileInput}
      type="file"
      multiple
      accept=".pdf,.docx,.odt,.txt,.md,.png,.jpg,.jpeg,.gif,.bmp,.tiff"
      class="hidden"
      onchange={handleFileSelect}
    />
    <div class="space-y-2">
      <p class="text-4xl">📄</p>
      <p class="text-gray-600 dark:text-gray-300 font-medium">
        {uploading ? t('documents.uploading') : t('documents.dragDrop')}
      </p>
      <p class="text-xs text-gray-500 dark:text-gray-400">
        {t('documents.supportedFormats')}
      </p>
      {#if ocrAvailable === true}
        <p class="text-xs text-green-600 dark:text-green-400">✅ OCR available — images supported</p>
      {:else if ocrAvailable === false}
        <p class="text-xs text-orange-500 dark:text-orange-400">⚠️ OCR not available — image upload may produce empty text</p>
      {/if}
    </div>
  </div>

  <!-- RAG Search Panel -->
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-4 border border-gray-200 dark:border-gray-700">
    <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center gap-2">
      🔍 {t('rag.search')}
    </h3>
    <form onsubmit={(e) => { e.preventDefault(); handleRAGSearch(); }} class="flex gap-2">
      <input
        type="text"
        bind:value={searchQuery}
        placeholder={t('rag.searchPlaceholder')}
        class="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
               bg-white dark:bg-gray-700 text-gray-900 dark:text-white
               focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
      />
      <select
        bind:value={searchLimit}
        class="px-2 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
               bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
      >
        <option value={3}>3</option>
        <option value={5}>5</option>
        <option value={10}>10</option>
        <option value={20}>20</option>
      </select>
      <button
        type="submit"
        class="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700
               transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        disabled={isSearching || !searchQuery.trim()}
      >
        {#if isSearching}
          <span class="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
        {/if}
        {t('rag.searchButton')}
      </button>
    </form>

    {#if searchError}
      <p class="mt-2 text-sm text-red-600 dark:text-red-400">{searchError}</p>
    {/if}

    {#if searchResults}
      {#if searchResults.results?.length > 0}
        <div class="mt-3 space-y-2">
          {#each searchResults.results as result, i}
            <div class="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg border border-gray-200 dark:border-gray-600">
              <div class="flex items-center justify-between mb-1">
                <span class="text-xs font-medium text-gray-700 dark:text-gray-300">
                  {t('rag.source')}: <span class="font-mono">{result.document_id || result.filename || '—'}</span>
                </span>
                {#if result.score !== undefined}
                  <span class="px-2 py-0.5 text-xs rounded-full bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
                    {t('rag.relevance')}: {(result.score * 100).toFixed(1)}%
                  </span>
                {/if}
              </div>
              {#if result.chunk_index !== undefined}
                <p class="text-xs text-gray-500 dark:text-gray-400 mb-1">{t('rag.chunk')} #{result.chunk_index}</p>
              {/if}
              <p class="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{result.text || result.content || '—'}</p>
            </div>
          {/each}
        </div>
      {:else}
        <p class="mt-3 text-sm text-gray-500 dark:text-gray-400 text-center">{t('rag.noResults')}</p>
      {/if}
    {/if}
  </div>

  <!-- Documents table -->
  {#if loading}
    <div class="text-center py-8 text-gray-500 dark:text-gray-400">
      {t('common.loading')}
    </div>
  {:else if documents.length === 0}
    <div class="text-center py-8 text-gray-500 dark:text-gray-400">
      {t('documents.noDocuments')}
    </div>
  {:else}
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
      <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
        <thead class="bg-gray-50 dark:bg-gray-700">
          <tr>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
              {t('documents.filename')}
            </th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
              {t('documents.fileSize')}
            </th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
              {t('documents.fileType')}
            </th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
              {t('documents.uploadedAt')}
            </th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
              {t('documents.ragStatus')}
            </th>
            <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
              {t('documents.actions')}
            </th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-200 dark:divide-gray-700">
          {#each documents as doc (doc.id)}
            <tr class="hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
              <td class="px-4 py-3 whitespace-nowrap">
                <div class="flex items-center">
                  <span class="text-lg mr-2">{getFileIcon(doc.filename)}</span>
                  <span class="text-sm font-medium text-gray-800 dark:text-gray-200" title={doc.filename}>
                    {doc.filename}
                  </span>
                </div>
              </td>
              <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                {formatFileSize(doc.file_size)}
              </td>
              <td class="px-4 py-3 whitespace-nowrap">
                {#if doc.file_type}
                  <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700 dark:bg-gray-600 dark:text-gray-300">
                    {doc.file_type.toUpperCase()}
                  </span>
                {:else}
                  <span class="text-sm text-gray-400 dark:text-gray-500">—</span>
                {/if}
              </td>
              <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                {formatDate(doc.uploaded_at)}
              </td>
              <td class="px-4 py-3 whitespace-nowrap">
                <button
                  class="inline-flex items-center gap-1 px-3 py-1 rounded-lg text-xs font-medium transition-colors cursor-pointer border
                    {doc.in_rag
                      ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300 hover:bg-green-200 dark:hover:bg-green-900/50 border-green-300 dark:border-green-700'
                      : 'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 hover:bg-blue-100 dark:hover:bg-blue-900/50 border-blue-300 dark:border-blue-700'}"
                  onclick={() => toggleRAG(doc)}
                  title={doc.in_rag ? t('documents.removeFromRAG') : t('documents.addToRAG')}
                >
                  {#if doc.in_rag}
                    ✓ {t('documents.inRAG')} ✕
                  {:else}
                    ＋ {t('documents.addToRAG')}
                  {/if}
                </button>
              </td>
              <td class="px-4 py-3 whitespace-nowrap text-right text-sm space-x-2">
                <button
                  class="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 transition-colors"
                  onclick={() => viewDocument(doc)}
                  title={t('documents.view')}
                >
                  👁️
                </button>
                <button
                  class="text-amber-600 hover:text-amber-800 dark:text-amber-400 dark:hover:text-amber-300 transition-colors"
                  onclick={() => openMoveDialog(doc)}
                  title="Move to another project"
                >
                  📦
                </button>
                <button
                  class="text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300 transition-colors"
                  onclick={() => handleDelete(doc)}
                  title={t('documents.delete')}
                >
                  🗑️
                </button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<!-- Document Viewer Modal -->
{#if viewingDoc}
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions a11y_interactive_supports_focus -->
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onclick={(e) => { if (e.target === e.currentTarget) closeViewer(); }} role="dialog" aria-modal="true" tabindex="-1">
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-3xl w-full mx-4 max-h-[80vh] flex flex-col">
      <!-- Header -->
      <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <div class="flex items-center gap-3">
          <span class="text-2xl">{getFileIcon(viewingDoc.filename)}</span>
          <div>
            <h2 class="text-lg font-semibold text-gray-800 dark:text-white">{viewingDoc.filename}</h2>
            <p class="text-xs text-gray-500 dark:text-gray-400">
              {formatFileSize(viewingDoc.file_size)}
              {#if viewingDoc.file_type} · {viewingDoc.file_type.toUpperCase()}{/if}
              · {t('documents.uploadedAt')}: {formatDate(viewingDoc.uploaded_at)}
            </p>
          </div>
        </div>
        <button
          class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-2xl"
          onclick={closeViewer}
          title={t('common.close')}
        >
          ✕
        </button>
      </div>

      <!-- Content -->
      <div class="flex-1 overflow-y-auto p-6">
        {#if viewingLoading}
          <div class="text-center py-8 text-gray-500 dark:text-gray-400">
            {t('common.loading')}
          </div>
        {:else if viewingDocContent}
          <!-- RAG status -->
          <div class="mb-4 flex items-center gap-3">
            <button
              class="inline-flex items-center gap-1 px-4 py-1.5 rounded-lg text-sm font-medium transition-colors cursor-pointer border
                {viewingDocContent.in_rag
                  ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300 hover:bg-green-200 border-green-300 dark:border-green-700'
                  : 'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 hover:bg-blue-100 dark:hover:bg-blue-900/50 border-blue-300 dark:border-blue-700'}"
              onclick={() => {
                toggleRAG(viewingDoc);
                viewingDocContent = { ...viewingDocContent, in_rag: !viewingDocContent.in_rag };
              }}
            >
              {#if viewingDocContent.in_rag}
                ✓ {t('documents.inRAG')} ✕
              {:else}
                ＋ {t('documents.addToRAG')}
              {/if}
            </button>
            {#if viewingDocContent.chunk_count > 0}
              <span class="text-xs text-gray-500 dark:text-gray-400">
                {viewingDocContent.chunk_count} {t('documents.chunks')}
              </span>
            {/if}
          </div>

          <!-- Document text content -->
          {#if viewingDocContent.text_content}
            <div class="bg-gray-50 dark:bg-gray-900 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
              <pre class="whitespace-pre-wrap text-sm text-gray-700 dark:text-gray-300 font-mono leading-relaxed">{viewingDocContent.text_content}</pre>
            </div>
          {:else}
            <div class="text-center py-8 text-gray-500 dark:text-gray-400">
              {t('documents.noContent')}
            </div>
          {/if}
        {/if}
      </div>
    </div>
  </div>
{/if}

<!-- Move Document Dialog -->
{#if moveDialogOpen && moveDoc}
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions a11y_interactive_supports_focus -->
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onclick={(e) => { if (e.target === e.currentTarget) closeMoveDialog(); }} role="dialog" aria-modal="true" tabindex="-1">
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
      <h2 class="text-lg font-semibold text-gray-800 dark:text-white mb-2">
        Move Document
      </h2>
      <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">
        Move <strong>{moveDoc.filename}</strong> to another project:
      </p>

      {#if moveError}
        <div class="mb-3 text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 px-3 py-2 rounded">{moveError}</div>
      {/if}

      <div class="space-y-2 mb-6 max-h-48 overflow-y-auto">
        {#each moveProjects as p}
          <label class="flex items-center gap-3 p-2 rounded hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer {moveTargetId === p.id ? 'bg-blue-50 dark:bg-blue-900/20 ring-1 ring-blue-300 dark:ring-blue-700' : ''}">
            <input type="radio" name="targetProject" value={p.id} bind:group={moveTargetId} class="accent-blue-600" />
            <div>
              <span class="text-sm font-medium text-gray-800 dark:text-gray-200">{p.name}</span>
              {#if p.description}
                <p class="text-xs text-gray-400 dark:text-gray-500">{p.description}</p>
              {/if}
            </div>
          </label>
        {/each}
        {#if moveProjects.length === 0 && !moveError}
          <p class="text-sm text-gray-400 dark:text-gray-500 text-center py-4">No other projects available</p>
        {/if}
      </div>

      <div class="flex justify-end gap-2">
        <button
          class="px-4 py-2 text-sm rounded-lg bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
          onclick={closeMoveDialog}
        >
          Cancel
        </button>
        <button
          class="px-4 py-2 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors disabled:opacity-50"
          disabled={!moveTargetId || moveSaving}
          onclick={confirmMove}
        >
          {moveSaving ? 'Moving…' : 'Move'}
        </button>
      </div>
    </div>
  </div>
{/if}
