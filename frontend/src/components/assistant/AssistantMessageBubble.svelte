<script>
  import { marked } from 'marked';
  import DOMPurify from 'dompurify';

  let { message } = $props();

  function renderMarkdown(text) {
    if (!text) return '';
    const raw = marked.parse(text);
    return DOMPurify.sanitize(raw, {
      USE_PROFILES: { html: true },
      ALLOWED_ATTR: ['href', 'title', 'target', 'rel', 'class', 'id', 'name', 'src', 'alt'],
    });
  }
</script>

<div
  class="message"
  class:user={message.role === 'user'}
  class:assistant={message.role === 'assistant'}
  class:tool={message.role === 'tool'}
>
  <div class="message-content">
    {#if message.role === 'assistant'}
      <div class="markdown-content">{@html renderMarkdown(message.content)}</div>
    {:else if message.role === 'tool'}
      <div class="tool-result">
        <span class="tool-badge">
          🔧 {message.tool_name || 'Tool'}
        </span>
        <pre class="tool-output">{message.content}</pre>
      </div>
    {:else}
      <p>{message.content}</p>
    {/if}
  </div>
  <div class="message-meta">
    {#if message.model}
      <span class="model-badge">{message.model}</span>
    {/if}
  </div>
</div>

<style>
  .message {
    display: flex;
    flex-direction: column;
    max-width: 80%;
  }

  .message.user {
    align-self: flex-end;
  }

  .message.assistant {
    align-self: flex-start;
  }

  .message-content {
    padding: 10px 14px;
    border-radius: 12px;
    font-size: 14px;
    line-height: 1.5;
  }

  .message.user .message-content {
    background: #667eea;
    color: white;
    border-bottom-right-radius: 4px;
  }

  .message.assistant .message-content {
    background: #f3f4f6;
    color: #1f2937;
    border-bottom-left-radius: 4px;
  }

  .message.tool {
    align-self: center;
    max-width: 90%;
  }

  .message.tool .message-content {
    background: #fef3c7;
    color: #92400e;
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 12px;
  }

  .tool-result {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .tool-badge {
    font-size: 11px;
    font-weight: 600;
    opacity: 0.8;
  }

  .tool-output {
    font-size: 11px;
    font-family: monospace;
    white-space: pre-wrap;
    word-break: break-all;
    max-height: 100px;
    overflow-y: auto;
    margin: 0;
    background: rgba(0,0,0,0.05);
    padding: 4px 6px;
    border-radius: 4px;
  }

  .markdown-content {
    font-size: 14px;
  }

  .markdown-content :global(p) {
    margin: 0 0 8px 0;
  }

  .markdown-content :global(p:last-child) {
    margin-bottom: 0;
  }

  .markdown-content :global(ul),
  .markdown-content :global(ol) {
    margin: 8px 0;
    padding-left: 20px;
  }

  .markdown-content :global(li) {
    margin: 2px 0;
  }

  .markdown-content :global(code) {
    background: #e5e7eb;
    padding: 2px 4px;
    border-radius: 3px;
    font-size: 13px;
  }

  .markdown-content :global(pre) {
    background: #1f2937;
    color: #f9fafb;
    padding: 12px;
    border-radius: 6px;
    overflow-x: auto;
    margin: 8px 0;
  }

  .markdown-content :global(pre code) {
    background: none;
    padding: 0;
    color: inherit;
  }

  .message-meta {
    margin-top: 4px;
    font-size: 11px;
    color: #9ca3af;
  }

  .model-badge {
    background: #e5e7eb;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 10px;
  }

  :global(.dark) .message.assistant .message-content {
    background: #374151;
    color: #e5e7eb;
  }

  :global(.dark) .message.tool .message-content {
    background: #78350f;
    color: #fde68a;
  }

  :global(.dark) .tool-output {
    background: rgba(255, 255, 255, 0.08);
  }

  :global(.dark) .markdown-content :global(code) {
    background: #4b5563;
  }

  :global(.dark) .model-badge {
    background: #4b5563;
    color: #d1d5db;
  }
</style>
