<script>
  import { onMount, onDestroy } from 'svelte';
  import {
    createAssistantSession,
    listAssistantSessions,
    getAssistantSession,
    deleteAssistantSession,
    sendAssistantMessage,
  } from '../lib/api.js';
  import { i18n, locale, tStore } from '../lib/i18n/index.js';
  import AssistantSessionList from './assistant/AssistantSessionList.svelte';
  import AssistantMessageBubble from './assistant/AssistantMessageBubble.svelte';
  import AssistantTypingIndicator from './assistant/AssistantTypingIndicator.svelte';
  import AssistantInputBar from './assistant/AssistantInputBar.svelte';

  let t = $derived($tStore);

  let { isOpen = false, isMinimized = false, onclose = () => {} } = $props();

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

  // Safety net: if the component unmounts mid-drag/mid-resize, the user
  // releases the mouse outside the page, or the chat panel is closed by
  // some other code path, make sure none of the document-level listeners
  // leak. removeEventListener is a no-op when the listener isn't there.
  onDestroy(() => {
    stopResize();
    stopDrag();
    stopResizeWidth();
    stopResizeRight();
    stopResizeBottom();
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
      messages = messages.slice(0, -1);
    } finally {
      isLoading = false;
    }
  }

  function scrollToBottom() {
    setTimeout(() => {
      if (chatContainer) {
        chatContainer.scrollTop = chatContainer.scrollHeight;
      }
    }, 50);
  }

  // Resize handlers
  let startTop = $state(null);

  function startResize(event) {
    isResizing = true;
    startY = event.clientY || event.touches?.[0]?.clientY;
    startHeight = chatHeight;
    startTop = chatPos.top;
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
    if (startTop !== null) {
      chatPos = { ...chatPos, top: startTop - delta };
    }
  }

  function stopResize() {
    isResizing = false;
    document.removeEventListener('mousemove', onResize);
    document.removeEventListener('mouseup', stopResize);
    document.removeEventListener('touchmove', onResize);
    document.removeEventListener('touchend', stopResize);
  }

  let chatWidth = $state(700);
  let chatPos = $state({ top: null, left: null });
  let isDragging = $state(false);
  let dragStart = $state({ x: 0, y: 0, top: 0, left: 0 });
  let isResizingWidth = $state(false);
  let resizeWidthStart = $state({ x: 0, w: 0 });
  const MIN_WIDTH = 320;
  const MAX_WIDTH = 1200;

  function getChatStyle() {
    let s = `height: ${isMinimized ? 'auto' : chatHeight + 'px'}; width: ${chatWidth}px; `;
    if (chatPos.top !== null) {
      s += `top: ${chatPos.top}px; left: ${chatPos.left}px; `;
    } else {
      s += `bottom: 0; right: 20px; `;
    }
    return s;
  }

  function startDrag(event) {
    if (event.target.closest('button')) return;
    isDragging = true;
    const clientX = event.clientX || event.touches?.[0]?.clientX;
    const clientY = event.clientY || event.touches?.[0]?.clientY;
    dragStart.x = clientX;
    dragStart.y = clientY;
    const chatEl = event.currentTarget.closest('.assistant-chat');
    if (!chatEl) return;
    const rect = chatEl.getBoundingClientRect();
    chatPos = { top: rect.top, left: rect.left };
    dragStart.top = rect.top;
    dragStart.left = rect.left;
    document.addEventListener('mousemove', onDrag);
    document.addEventListener('mouseup', stopDrag);
    document.addEventListener('touchmove', onDrag);
    document.addEventListener('touchend', stopDrag);
    event.preventDefault();
  }

  function onDrag(event) {
    if (!isDragging) return;
    const clientX = event.clientX || event.touches?.[0]?.clientX;
    const clientY = event.clientY || event.touches?.[0]?.clientY;
    chatPos = {
      top: Math.max(0, dragStart.top + (clientY - dragStart.y)),
      left: Math.max(0, dragStart.left + (clientX - dragStart.x)),
    };
  }

  function stopDrag() {
    isDragging = false;
    document.removeEventListener('mousemove', onDrag);
    document.removeEventListener('mouseup', stopDrag);
    document.removeEventListener('touchmove', onDrag);
    document.removeEventListener('touchend', stopDrag);
  }

  function startResizeWidth(event) {
    isResizingWidth = true;
    resizeWidthStart.x = event.clientX || event.touches?.[0]?.clientX;
    resizeWidthStart.w = chatWidth;
    document.addEventListener('mousemove', onResizeWidth);
    document.addEventListener('mouseup', stopResizeWidth);
    document.addEventListener('touchmove', onResizeWidth);
    document.addEventListener('touchend', stopResizeWidth);
    event.preventDefault();
  }

  function onResizeWidth(event) {
    if (!isResizingWidth) return;
    const clientX = event.clientX || event.touches?.[0]?.clientX;
    const delta = resizeWidthStart.x - clientX;
    chatWidth = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, resizeWidthStart.w + delta));
    if (chatPos.left !== null) {
      chatPos = { ...chatPos, left: chatPos.left - delta };
    }
  }

  function stopResizeWidth() {
    isResizingWidth = false;
    document.removeEventListener('mousemove', onResizeWidth);
    document.removeEventListener('mouseup', stopResizeWidth);
    document.removeEventListener('touchmove', onResizeWidth);
    document.removeEventListener('touchend', stopResizeWidth);
  }

  // Right resize (width from right edge)
  let isResizingRight = $state(false);
  let resizeRightStart = $state({ x: 0, w: 0 });

  function startResizeRight(event) {
    isResizingRight = true;
    resizeRightStart.x = event.clientX || event.touches?.[0]?.clientX;
    resizeRightStart.w = chatWidth;
    if (chatPos.top === null) {
      const chatEl = event.currentTarget.closest('.assistant-chat');
      if (chatEl) {
        const rect = chatEl.getBoundingClientRect();
        chatPos = { top: rect.top, left: rect.left };
      }
    }
    document.addEventListener('mousemove', onResizeRight);
    document.addEventListener('mouseup', stopResizeRight);
    document.addEventListener('touchmove', onResizeRight);
    document.addEventListener('touchend', stopResizeRight);
    event.preventDefault();
  }

  function onResizeRight(event) {
    if (!isResizingRight) return;
    const clientX = event.clientX || event.touches?.[0]?.clientX;
    const delta = clientX - resizeRightStart.x;
    chatWidth = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, resizeRightStart.w + delta));
  }

  function stopResizeRight() {
    isResizingRight = false;
    document.removeEventListener('mousemove', onResizeRight);
    document.removeEventListener('mouseup', stopResizeRight);
    document.removeEventListener('touchmove', onResizeRight);
    document.removeEventListener('touchend', stopResizeRight);
  }

  // Bottom resize (height from bottom edge)
  let isResizingBottom = $state(false);
  let resizeBottomStart = $state({ y: 0, h: 0 });

  function startResizeBottom(event) {
    isResizingBottom = true;
    resizeBottomStart.y = event.clientY || event.touches?.[0]?.clientY;
    resizeBottomStart.h = chatHeight;
    if (chatPos.top === null) {
      const chatEl = event.currentTarget.closest('.assistant-chat');
      if (chatEl) {
        const rect = chatEl.getBoundingClientRect();
        chatPos = { top: rect.top, left: rect.left };
      }
    }
    document.addEventListener('mousemove', onResizeBottom);
    document.addEventListener('mouseup', stopResizeBottom);
    document.addEventListener('touchmove', onResizeBottom);
    document.addEventListener('touchend', stopResizeBottom);
    event.preventDefault();
  }

  function onResizeBottom(event) {
    if (!isResizingBottom) return;
    const clientY = event.clientY || event.touches?.[0]?.clientY;
    const delta = clientY - resizeBottomStart.y;
    chatHeight = Math.max(MIN_HEIGHT, Math.min(MAX_HEIGHT, resizeBottomStart.h + delta));
  }

  function stopResizeBottom() {
    isResizingBottom = false;
    document.removeEventListener('mousemove', onResizeBottom);
    document.removeEventListener('mouseup', stopResizeBottom);
    document.removeEventListener('touchmove', onResizeBottom);
    document.removeEventListener('touchend', stopResizeBottom);
  }

  function toggleMinimize() {
    isMinimized = !isMinimized;
  }

  function close() {
    onclose();
  }
</script>

{#if isOpen}
  <div class="assistant-chat" class:minimized={isMinimized} class:dragging={isDragging} style={getChatStyle()}>
    {#if !isMinimized}
      <div class="resize-handle resize-handle--height" onmousedown={startResize} ontouchstart={startResize}></div>
    {/if}
    <!-- Header -->
    <div class="chat-header" onmousedown={startDrag} ontouchstart={startDrag}>
      <div class="header-left">
        <span class="chat-icon">🦊</span>
        <span class="chat-title">Danwa Kitsune</span>
      </div>
      <div class="header-actions">
        <button class="btn-icon" onclick={toggleMinimize} title={isMinimized ? t('kitsune.open') : t('kitsune.minimize')}>
          {isMinimized ? '▲' : '▼'}
        </button>
        <button class="btn-icon" onclick={close} title={t('common.close')}>✕</button>
      </div>
    </div>

    {#if !isMinimized}
      <div class="resize-handle resize-handle--left" onmousedown={startResizeWidth} ontouchstart={startResizeWidth}></div>
      <div class="resize-handle resize-handle--right" onmousedown={startResizeRight} ontouchstart={startResizeRight}></div>
      <div class="resize-handle resize-handle--bottom" onmousedown={startResizeBottom} ontouchstart={startResizeBottom}></div>

      <div class="chat-body">
        <AssistantSessionList
          {sessions}
          activeSessionId={currentSession?.id}
          onSelect={selectSession}
          onNew={createNewSession}
          onDelete={deleteSession}
          {t}
        />

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
                <AssistantMessageBubble {message} />
              {/each}
            {/if}

            {#if isLoading}
              <AssistantTypingIndicator />
            {/if}

            {#if error}
              <div class="error-message">{error}</div>
            {/if}
          </div>

          <!-- Input area -->
          <AssistantInputBar
            bind:value={newMessage}
            disabled={isLoading}
            placeholder={t('kitsune.placeholder')}
            onSend={sendMessage}
          />
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
    min-width: 320px;
    max-width: calc(100vw - 40px);
    background: white;
    border-radius: 12px 12px 0 0;
    box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.15);
    display: flex;
    flex-direction: column;
    z-index: 1000;
    overflow: hidden;
  }

  .assistant-chat.minimized {
    height: auto !important;
  }

  .assistant-chat.dragging {
    transition: none;
    user-select: none;
  }

  .chat-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    cursor: grab;
    user-select: none;
  }

  .assistant-chat.dragging .chat-header {
    cursor: grabbing;
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

  .resize-handle--height {
    position: absolute;
    top: -6px;
    left: 0;
    right: 0;
    height: 10px;
    background: transparent;
    cursor: ns-resize;
    transition: background 0.2s;
    z-index: 10;
  }

  .resize-handle--height:hover {
    background: rgba(102, 126, 234, 0.2);
  }

  .resize-handle--left,
  .resize-handle--right {
    position: absolute;
    top: 0;
    bottom: 0;
    width: 4px;
    background: transparent;
    cursor: ew-resize;
    transition: background 0.2s;
    z-index: 10;
  }

  .resize-handle--left {
    left: 0;
  }

  .resize-handle--right {
    right: 0;
  }

  .resize-handle--left:hover,
  .resize-handle--left:active,
  .resize-handle--right:hover,
  .resize-handle--right:active {
    background: #667eea;
  }

  .resize-handle--bottom {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 4px;
    background: transparent;
    cursor: ns-resize;
    transition: background 0.2s;
    z-index: 10;
  }

  .resize-handle--bottom:hover {
    background: rgba(102, 126, 234, 0.2);
  }

  .chat-body {
    display: flex;
    flex: 1;
    overflow: hidden;
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

  .error-message {
    background: #fee2e2;
    color: #dc2626;
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 13px;
    text-align: center;
  }

  :global(.dark) .assistant-chat {
    background: #1f2937;
    box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.4);
  }

  :global(.dark) .chat-header {
    background: linear-gradient(135deg, #4f46e5 0%, #6b21a8 100%);
  }

  :global(.dark) .resize-handle--left:hover,
  :global(.dark) .resize-handle--left:active,
  :global(.dark) .resize-handle--right:hover,
  :global(.dark) .resize-handle--right:active,
  :global(.dark) .resize-handle--height:hover,
  :global(.dark) .resize-handle--bottom:hover {
    background: rgba(96, 165, 250, 0.3);
  }

  :global(.dark) .welcome-message {
    color: #9ca3af;
  }

  :global(.dark) .welcome-message h3 {
    color: #e5e7eb;
  }

  :global(.dark) .error-message {
    background: #7f1d1d;
    color: #fca5a5;
  }

  @media (max-width: 768px) {
    :global(.dark) .assistant-chat {
      background: #111827;
    }
  }

  /* Responsive */
  @media (max-width: 768px) {
    .assistant-chat {
      right: 0;
      width: 100% !important;
      max-width: 100%;
      border-radius: 0;
    }

    .resize-handle--left,
    .resize-handle--right,
    .resize-handle--bottom {
      display: none;
    }

    .chat-header {
      cursor: default;
    }
  }
</style>
