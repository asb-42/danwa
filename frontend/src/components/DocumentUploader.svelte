<script>
  // Placeholder — will handle document uploads for DMS in Sprint 3
  export let onUpload = null;

  let dragOver = false;

  function handleDrop(event) {
    event.preventDefault();
    dragOver = false;
    // Placeholder — actual upload logic in Sprint 3
    console.log('Files dropped:', event.dataTransfer.files);
  }

  function handleDragOver(event) {
    event.preventDefault();
    dragOver = true;
  }

  function handleDragLeave() {
    dragOver = false;
  }
</script>

<div
  class="border-2 border-dashed rounded-lg p-8 text-center transition-colors
    {dragOver
      ? 'border-blue-400 bg-blue-50 dark:bg-blue-900/20'
      : 'border-gray-300 dark:border-gray-600'}"
  on:drop={handleDrop}
  on:dragover={handleDragOver}
  on:dragleave={handleDragLeave}
  role="region"
  aria-label="Document upload area"
>
  <div class="space-y-2">
    <p class="text-gray-400 dark:text-gray-500 font-medium">📄 Document Upload</p>
    <p class="text-xs text-gray-400 dark:text-gray-500">
      Drag & drop files here or click to browse — Sprint 3
    </p>
  </div>
</div>
