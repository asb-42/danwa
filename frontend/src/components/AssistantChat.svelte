<script>
  import { createEventDispatcher, onMount } from 'svelte';
  import {
    createAssistantSession,
    listAssistantSessions,
    getAssistantSession,
    deleteAssistantSession,
    sendAssistantMessage,
  } from '../lib/api.js';
  import { marked } from 'marked';
  import { locale } from '../lib/i18n/index.js';

  const dispatch = createEventDispatcher();

  let { isOpen = false, isMinimized = false } = $props();

  const WELCOME = {
    en: {
      greeting: '🦊 Hello! I\'m Danwa Kitsune',
      subtitle: 'Your intelligent companion for the Danwa Debate Engine system.',
      ask: 'Ask me about:',
      items: [
        'How to start a debate',
        'Configuring LLM profiles',
        'Using the Blueprint Canvas',
        'Installing and managing modules',
        'And much more...',
      ],
    },
    de: {
      greeting: '🦊 Konnichiwa! Ich bin Danwa Kitsune',
      subtitle: 'Dein intelligenter Begleiter für das Danwa Debate Engine System.',
      ask: 'Frag mich nach:',
      items: [
        'Wie man eine Debatte startet',
        'LLM-Profile konfigurieren',
        'Blueprint Canvas verwenden',
        'Module installieren und verwalten',
        'Und vieles mehr...',
      ],
    },
  };

  let welcome = $derived(WELCOME[$locale] || WELCOME.en);

  let sessions = $state([]);
  let currentSession = $state(null);
  let messages = $state([]);
  let newMessage = $state('');
  let isLoading = $state(false);
  let error = $state(null);
  let chatContainer;

  // Resize state
  let chatHeight = $state(400);
  let isResizing = $state(false);
  let startY = $state(0);
  let startHeight = $state(0);
  const MIN_HEIGHT = 200;
  const MAX_HEIGHT = 800;

  onMount(async () => {
    if (isOpen) {
      await loadSessions();
    }
  });

  $effect(() => {
    if (isOpen && sessions.length === 0 && !currentSession) {
      createNewSession();
    }
  });

  async function loadSessions() {
    try {
      sessions = await listAssistantSessions();
    } catch (e) {
      error = 'Failed to load sessions';
    }
  }

  async function createNewSession() {
    try {
      currentSession = await createAssistantSession();
      messages = [];
      await loadSessions();
    } catch (e) {
      error = 'Failed to create session';
    }
  }

  async function selectSession(session) {
    currentSession = session;
    try {
      const full = await getAssistantSession(session.id);
      messages = full.messages || [];
      scrollToBottom();
    } catch (e) {
      error = 'Failed to load session';
    }
  }

  async function deleteSession(session, event) {
    event.stopPropagation();
    try {
      await deleteAssistantSession(session.id);
      if (currentSession?.id === session.id) {
        currentSession = null;
        messages = [];
      }
      await loadSessions();
      if (sessions.length === 0) {
        await createNewSession();
      }
    } catch (e) {
      error = 'Failed to delete session';
    }
  }

  async function sendMessage() {
    if (!newMessage.trim() || !currentSession || isLoading) return;

    const userMsg = {
      role: 'user',
      content: newMessage.trim(),
      timestamp: Date.now() / 1000,
    };
    messages = [...messages, userMsg];
    const msgToSend = newMessage.trim();
    newMessage = '';
    isLoading = true;
    error = null;
    scrollToBottom();

    try {
      const response = await sendAssistantMessage(currentSession.id, msgToSend);

      if (response.messages && Array.isArray(response.messages)) {
        // New format: array of all messages from this turn
        const newMsgs = response.messages.map(m => ({
          role: m.role,
          content: m.content,
          timestamp: m.timestamp,
          model: m.model || '',
          tool_call_id: m.tool_call_id || '',
          tool_name: m.tool_name || '',
        }));
        messages = [...messages, ...newMsgs];
      } else if (response.content) {
        // Legacy format: single message
        messages = [...messages, {
          role: 'assistant',
          content: response.content,
          timestamp: response.timestamp,
          model: response.model || '',
        }];
      }
      await loadSessions();
      scrollToBottom();
    } catch (e) {
      error = e.message || 'Failed to send message';
      // Remove the user message on error
      messages = messages.slice(0, -1);
    } finally {
      isLoading = false;
    }
  }

  function handleKeydown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  }

  function scrollToBottom() {
    setTimeout(() => {
      if (chatContainer) {
        chatContainer.scrollTop = chatContainer.scrollHeight;
      }
    }, 50);
  }

  function renderMarkdown(text) {
    if (!text) return '';
    return marked.parse(text);
  }

  // Resize handlers
  function startResize(event) {
    isResizing = true;
    startY = event.clientY || event.touches?.[0]?.clientY;
    startHeight = chatHeight;
    document.addEventListener('mousemove', onResize);
    document.addEventListener('mouseup', stopResize);
    document.addEventListener('touchmove', onResize);
    document.addEventListener('touchend', stopResize);
    event.preventDefault();
  }

  function onResize(event) {
    if (!isResizing) return;
    const clientY = event.clientY || event.touches?.[0]?.clientY;
    const delta = startY - clientY;
    chatHeight = Math.max(MIN_HEIGHT, Math.min(MAX_HEIGHT, startHeight + delta));
  }

  function stopResize() {
    isResizing = false;
    document.removeEventListener('mousemove', onResize);
    document.removeEventListener('mouseup', stopResize);
    document.removeEventListener('touchmove', onResize);
    document.removeEventListener('touchend', stopResize);
  }

  function toggleMinimize() {
    isMinimized = !isMinimized;
  }

  function close() {
    dispatch('close');
  }
</script>

{#if isOpen}
  <div class="assistant-chat" class:minimized={isMinimized} style="height: {isMinimized ? 'auto' : chatHeight + 'px'}">
    <!-- Header -->
    <div class="chat-header">
      <div class="header-left">
        <span class="chat-icon">🦊</span>
        <span class="chat-title">Danwa Kitsune</span>
      </div>
      <div class="header-actions">
        <button class="btn-icon" onclick={toggleMinimize} title={isMinimized ? 'Öffnen' : 'Minimieren'}>
          {isMinimized ? '▲' : '▼'}
        </button>
        <button class="btn-icon" onclick={close} title="Schließen">✕</button>
      </div>
    </div>

    {#if !isMinimized}
      <!-- Resize handle -->
      <div class="resize-handle" onmousedown={startResize} ontouchstart={startResize}></div>

      <div class="chat-body">
        <!-- Session sidebar -->
        <div class="session-sidebar">
          <div class="session-header">
            <span>Konversationen</span>
            <button class="btn-new" onclick={createNewSession} title="Neue Konversation">+</button>
          </div>
          <div class="session-list">
            {#each sessions as session (session.id)}
              <div
                class="session-item"
                class:active={currentSession?.id === session.id}
                onclick={() => selectSession(session)}
              >
                <span class="session-title">{session.title || 'Neue Konversation'}</span>
                <button class="btn-delete" onclick={(e) => deleteSession(session, e)}>×</button>
              </div>
            {/each}
          </div>
        </div>

        <!-- Chat area -->
        <div class="chat-area">
          <div class="messages" bind:this={chatContainer}>
            {#if messages.length === 0}
              <div class="welcome-message">
                <h3>{welcome.greeting}</h3>
                <p>{welcome.subtitle}</p>
                <p>{welcome.ask}</p>
                <ul>
                  {#each welcome.items as item}
                    <li>{item}</li>
                  {/each}
                </ul>
              </div>
            {:else}
              {#each messages as message (message.timestamp + '-' + message.role + '-' + (message.tool_call_id || ''))}
                <div class="message"
                     class:user={message.role === 'user'}
                     class:assistant={message.role === 'assistant'}
                     class:tool={message.role === 'tool'}>
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
              {/each}
            {/if}

            {#if isLoading}
              <div class="message assistant">
                <div class="message-content">
                  <div class="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                </div>
              </div>
            {/if}

            {#if error}
              <div class="error-message">{error}</div>
            {/if}
          </div>

          <!-- Input area -->
          <div class="input-area">
            <textarea
              bind:value={newMessage}
              onkeydown={handleKeydown}
              placeholder="Frage den Danwa Assistenten..."
              rows="1"
              disabled={isLoading}
            ></textarea>
            <button
              class="btn-send"
              onclick={sendMessage}
              disabled={!newMessage.trim() || isLoading || !currentSession}
              title={!currentSession ? 'No active session' : ''}
            >
              ➤
            </button>
          </div>
        </div>
      </div>
    {/if}
  </div>
{/if}

<style>
  .assistant-chat {
    position: fixed;
    bottom: 0;
    right: 20px;
    width: 700px;
    max-width: calc(100vw - 40px);
    background: white;
    border-radius: 12px 12px 0 0;
    box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.15);
    display: flex;
    flex-direction: column;
    z-index: 1000;
    transition: height 0.2s ease;
    overflow: hidden;
  }

  .assistant-chat.minimized {
    height: auto !important;
  }

  .chat-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    cursor: pointer;
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .chat-icon {
    font-size: 20px;
  }

  .chat-title {
    font-weight: 600;
    font-size: 14px;
  }

  .header-actions {
    display: flex;
    gap: 4px;
  }

  .btn-icon {
    background: rgba(255, 255, 255, 0.2);
    border: none;
    color: white;
    width: 28px;
    height: 28px;
    border-radius: 6px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    transition: background 0.2s;
  }

  .btn-icon:hover {
    background: rgba(255, 255, 255, 0.3);
  }

  .resize-handle {
    height: 4px;
    background: #e5e7eb;
    cursor: ns-resize;
    transition: background 0.2s;
  }

  .resize-handle:hover {
    background: #667eea;
  }

  .chat-body {
    display: flex;
    flex: 1;
    overflow: hidden;
  }

  .session-sidebar {
    width: 180px;
    border-right: 1px solid #e5e7eb;
    display: flex;
    flex-direction: column;
    background: #f9fafb;
  }

  .session-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 12px;
    font-size: 12px;
    font-weight: 600;
    color: #374151;
    border-bottom: 1px solid #e5e7eb;
  }

  .btn-new {
    background: #667eea;
    color: white;
    border: none;
    width: 22px;
    height: 22px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 16px;
    line-height: 1;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .btn-new:hover {
    background: #5568d3;
  }

  .session-list {
    flex: 1;
    overflow-y: auto;
  }

  .session-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    cursor: pointer;
    border-bottom: 1px solid #f3f4f6;
    transition: background 0.2s;
  }

  .session-item:hover {
    background: #f3f4f6;
  }

  .session-item.active {
    background: #e0e7ff;
    border-left: 3px solid #667eea;
  }

  .session-title {
    font-size: 12px;
    color: #374151;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
  }

  .btn-delete {
    background: none;
    border: none;
    color: #9ca3af;
    cursor: pointer;
    font-size: 16px;
    padding: 0 4px;
    opacity: 0;
    transition: opacity 0.2s, color 0.2s;
  }

  .session-item:hover .btn-delete {
    opacity: 1;
  }

  .btn-delete:hover {
    color: #ef4444;
  }

  .chat-area {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .messages {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .welcome-message {
    text-align: center;
    padding: 40px 20px;
    color: #6b7280;
  }

  .welcome-message h3 {
    color: #374151;
    margin-bottom: 8px;
  }

  .welcome-message p {
    margin: 4px 0;
  }

  .welcome-message ul {
    text-align: left;
    margin: 12px auto;
    max-width: 300px;
  }

  .welcome-message li {
    margin: 4px 0;
  }

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

  .typing-indicator {
    display: flex;
    gap: 4px;
    padding: 4px 0;
  }

  .typing-indicator span {
    width: 6px;
    height: 6px;
    background: #9ca3af;
    border-radius: 50%;
    animation: typing 1.4s infinite;
  }

  .typing-indicator span:nth-child(2) {
    animation-delay: 0.2s;
  }

  .typing-indicator span:nth-child(3) {
    animation-delay: 0.4s;
  }

  @keyframes typing {
    0%, 60%, 100% {
      transform: translateY(0);
      opacity: 0.4;
    }
    30% {
      transform: translateY(-6px);
      opacity: 1;
    }
  }

  .error-message {
    background: #fee2e2;
    color: #dc2626;
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 13px;
    text-align: center;
  }

  .input-area {
    display: flex;
    gap: 8px;
    padding: 12px 16px;
    border-top: 1px solid #e5e7eb;
    background: white;
  }

  .input-area textarea {
    flex: 1;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 14px;
    resize: none;
    outline: none;
    font-family: inherit;
    max-height: 100px;
    overflow-y: auto;
  }

  .input-area textarea:focus {
    border-color: #667eea;
    box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.1);
  }

  .input-area textarea:disabled {
    background: #f9fafb;
    cursor: not-allowed;
  }

  .btn-send {
    background: #667eea;
    color: white;
    border: none;
    border-radius: 8px;
    width: 40px;
    height: 40px;
    cursor: pointer;
    font-size: 18px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background 0.2s;
  }

  .btn-send:hover:not(:disabled) {
    background: #5568d3;
  }

  .btn-send:disabled {
    background: #e5e7eb;
    cursor: not-allowed;
  }

  /* Responsive */
  @media (max-width: 768px) {
    .assistant-chat {
      right: 0;
      width: 100%;
      max-width: 100%;
      border-radius: 0;
    }

    .session-sidebar {
      width: 140px;
    }
  }
</style>
