<script>
  /** @type {string} */
  export let content = '';

  import { marked } from 'marked';

  // Configure marked for safe rendering
  marked.setOptions({
    breaks: true,
    gfm: true,
  });

  $: html = content ? marked.parse(content) : '';
</script>

{#if html}
  <div class="prose prose-sm dark:prose-invert max-w-none
              prose-headings:mt-3 prose-headings:mb-1.5
              prose-h1:text-lg prose-h2:text-base prose-h3:text-sm
              prose-p:my-1.5 prose-p:leading-relaxed
              prose-ul:my-1.5 prose-ol:my-1.5
              prose-li:my-0.5
              prose-strong:text-gray-800 dark:prose-strong:text-gray-100
              prose-code:text-xs prose-code:bg-gray-100 dark:prose-code:bg-gray-700
              prose-code:px-1 prose-code:py-0.5 prose-code:rounded
              prose-blockquote:border-l-blue-400 prose-blockquote:pl-3
              prose-blockquote:text-gray-600 dark:prose-blockquote:text-gray-400
              prose-table:text-sm
              prose-hr:my-3">
    {@html html}
  </div>
{/if}
