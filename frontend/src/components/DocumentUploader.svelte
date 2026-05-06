<script>
  import { i18n } from '../lib/i18n/index.js';
  import { uploadDocument } from '../lib/api.js';

  let { onUpload = null, compact = false } = $props();

  let dragOver = $state(false);
  let uploading = $state(false);
  let fileInput = $state(null);

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

  async function handleUpload(files) {
    if (!files || files.length === 0) return;
    uploading = true;
    try {
      const results = [];
      for (const file of files) {
        const result = await uploadDocument(file);
        results.push(result);
      }
      if (onUpload) onUpload(results);
    } catch (e) {
      console.error('Upload failed:', e);
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

<div
  class="border-2 border-dashed rounded-lg text-center transition-colors cursor-pointer
    {compact ? 'p-4' : 'p-8'}
    {dragOver
      ? 'border-blue-400 bg-blue-50 dark:bg-blue-900/20'
      : 'border-gray-300 dark:border-gray-600 hover:border-blue-300 dark:hover:border-blue-600'}"
  ondrop={handleDrop}
  ondragover={handleDragOver}
  ondragleave={handleDragLeave}
  onclick={() => fileInput?.click()}
  role="region"
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
