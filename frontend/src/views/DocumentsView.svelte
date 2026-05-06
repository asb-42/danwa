<script>
  import { onMount } from 'svelte';
  import { i18n } from '../lib/i18n/index.js';
  import { activeProject } from '../lib/stores.js';
  import { getDocuments, getDocument, uploadDocument, deleteDocument, addDocumentToRAG, removeDocumentFromRAG } from '../lib/api.js';

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
  });

  // Reload when project changes
  $effect(() => {
    if (projectId) {
      loadDocuments();
    }
  });

  async function handleUpload(files) {
    if (!files || files.length === 0) return;
    uploading = true;
    error = '';
    try {
      for (const file of files) {
        await uploadDocument(file);
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

<div class="max-w-5xl mx-auto p-6 space-y-6">
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
    </div>
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
                  <span class="text-sm font-medium text-gray-800 dark:text-gray-200 truncate max-w-[200px]" title={doc.filename}>
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
                  class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium transition-colors
                    {doc.in_rag
                      ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300 hover:bg-green-200 dark:hover:bg-green-900/50'
                      : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600'}"
                  onclick={() => toggleRAG(doc)}
                  title={doc.in_rag ? t('documents.removeFromRAG') : t('documents.addToRAG')}
                >
                  {doc.in_rag ? `✓ ${t('documents.inRAG')}` : t('documents.notInRAG')}
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
              class="inline-flex items-center px-3 py-1.5 rounded-full text-sm font-medium transition-colors
                {viewingDocContent.in_rag
                  ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300 hover:bg-green-200'
                  : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400 hover:bg-gray-200'}"
              onclick={() => {
                toggleRAG(viewingDoc);
                viewingDocContent = { ...viewingDocContent, in_rag: !viewingDocContent.in_rag };
              }}
            >
              {viewingDocContent.in_rag ? `✓ ${t('documents.inRAG')}` : t('documents.notInRAG')}
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
