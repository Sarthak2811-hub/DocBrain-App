const API_BASE = '/api/v1';
let currentToken = localStorage.getItem('access_token');
let currentUser = null;
let activeDocId = null;
let activeConversationId = null;
let pollInterval = null;
let documentsCache = [];

// ================= INITIAL CHECK ================= //
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    if (currentToken) {
        verifyTokenAndLoadApp();
    }
});

function setupEventListeners() {
    // Auth Forms
    document.getElementById('login-form').addEventListener('submit', handleLogin);
    document.getElementById('signup-form').addEventListener('submit', handleSignup);
    
    // File Upload Dropzone
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('file-input');
    
    dropzone.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', (e) => handleFileUpload(e.target.files[0]));
    
    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
    });
    
    dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
    
    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            handleFileUpload(e.dataTransfer.files[0]);
        }
    });

    // Chat Form
    document.getElementById('chat-form').addEventListener('submit', handleChatSubmit);

    // Textarea Auto-height and Shift+Enter Submit
    const chatInputBox = document.getElementById('chat-input-box');
    chatInputBox.addEventListener('input', function() {
        this.style.height = '0px';
        const newHeight = Math.min(this.scrollHeight, 150);
        this.style.height = newHeight + 'px';
        this.style.overflowY = newHeight >= 150 ? 'auto' : 'hidden';
    });
    chatInputBox.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            document.getElementById('chat-form').dispatchEvent(new Event('submit'));
        }
    });
}

// ================= AUTHENTICATION FLOW ================= //
function switchAuthTab(tab) {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.auth-form').forEach(form => form.classList.remove('active'));
    
    if (tab === 'login') {
        document.getElementById('tab-login').classList.add('active');
        document.getElementById('login-form').classList.add('active');
    } else {
        document.getElementById('tab-signup').classList.add('active');
        document.getElementById('signup-form').classList.add('active');
    }
}

async function verifyTokenAndLoadApp() {
    try {
        const res = await fetch(`${API_BASE}/auth/me`, {
            headers: { 'Authorization': `Bearer ${currentToken}` }
        });
        if (res.ok) {
            currentUser = await res.json();
            showView('main-view');
            document.getElementById('user-display').textContent = currentUser.email;
            loadDocuments();
            loadConversations();
        } else {
            logout();
        }
    } catch (e) {
        logout();
    }
}

async function handleLogin(e) {
    e.preventDefault();
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;
    const errPanel = document.getElementById('auth-error');
    errPanel.style.display = 'none';

    // OAuth2 Standard Form input format (Form Data)
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);

    try {
        const res = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: formData
        });
        
        const data = await res.json();
        if (res.ok) {
            currentToken = data.access_token;
            localStorage.setItem('access_token', currentToken);
            verifyTokenAndLoadApp();
        } else {
            errPanel.textContent = data.detail || 'Login failed. Please check credentials.';
            errPanel.style.display = 'block';
        }
    } catch (err) {
        errPanel.textContent = 'Server connection failed.';
        errPanel.style.display = 'block';
    }
}

async function handleSignup(e) {
    e.preventDefault();
    const email = document.getElementById('signup-email').value;
    const password = document.getElementById('signup-password').value;
    const errPanel = document.getElementById('auth-error');
    errPanel.style.display = 'none';

    try {
        const res = await fetch(`${API_BASE}/auth/signup`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        
        const data = await res.json();
        if (res.ok) {
            // Automatically log in on signup
            document.getElementById('login-email').value = email;
            document.getElementById('login-password').value = password;
            document.getElementById('login-form').dispatchEvent(new Event('submit'));
        } else {
            errPanel.textContent = data.detail || 'Signup failed.';
            errPanel.style.display = 'block';
        }
    } catch (err) {
        errPanel.textContent = 'Server connection failed.';
        errPanel.style.display = 'block';
    }
}

function logout() {
    currentToken = null;
    currentUser = null;
    activeDocId = null;
    activeConversationId = null;
    localStorage.removeItem('access_token');
    showView('auth-view');
    if (pollInterval) clearInterval(pollInterval);
    
    // Collapse preview panel on logout
    const panel = document.getElementById('doc-preview-panel');
    if (panel) {
        panel.classList.add('collapsed');
        const toggleBtn = document.getElementById('toggle-preview-btn');
        if (toggleBtn) {
            toggleBtn.innerHTML = '<i class="fa-solid fa-eye"></i> <span>Show Document</span>';
        }
    }
}

function showView(viewId) {
    document.querySelectorAll('.view-panel').forEach(v => v.classList.remove('active'));
    document.getElementById(viewId).classList.add('active');
}

// ================= DOCUMENTS PIPELINE ================= //
async function loadDocuments() {
    try {
        const res = await fetch(`${API_BASE}/documents/`, {
            headers: { 'Authorization': `Bearer ${currentToken}` }
        });
        if (!res.ok) return;
        const docs = await res.json();
        documentsCache = docs;
        renderDocumentsList(docs);
        
        // Auto check if polling needed (for pending/processing jobs)
        const hasUnfinishedJobs = docs.some(d => d.status === 'pending' || d.status === 'processing');
        if (hasUnfinishedJobs && !pollInterval) {
            pollInterval = setInterval(loadDocuments, 3000);
        } else if (!hasUnfinishedJobs && pollInterval) {
            clearInterval(pollInterval);
            pollInterval = null;
        }
        updateChatHeader();
    } catch (e) {
        console.error('Failed to load documents', e);
    }
}

function renderDocumentsList(docs) {
    const list = document.getElementById('documents-list');
    list.innerHTML = '';
    
    docs.forEach(doc => {
        const li = document.createElement('li');
        li.className = `list-item ${activeDocId === doc.id ? 'active' : ''}`;
        li.setAttribute('onclick', `selectDocument(${doc.id})`);
        
        let fileIcon = 'fa-file-pdf';
        const filename = doc.original_filename.toLowerCase();
        if (filename.endsWith('.txt')) {
            fileIcon = 'fa-file-lines';
        } else if (filename.endsWith('.docx')) {
            fileIcon = 'fa-file-word';
        }

        let statusBadge = `<span class="status-badge status-${doc.status}">${doc.status}</span>`;
        
        li.innerHTML = `
            <div class="item-info">
                <i class="fa-solid ${fileIcon}"></i>
                <span title="${doc.original_filename}">${doc.original_filename}</span>
            </div>
            <div style="display: flex; gap: 8px; align-items: center;">
                ${statusBadge}
                <button class="delete-item-btn" onclick="event.stopPropagation(); deleteDocument(${doc.id})">
                    <i class="fa-regular fa-trash-can"></i>
                </button>
            </div>
        `;
        list.appendChild(li);
    });
}

async function handleFileUpload(file) {
    if (!file) return;
    
    const allowedExtensions = ['.pdf', '.txt', '.docx'];
    const fileNameLower = file.name.toLowerCase();
    const isAllowed = allowedExtensions.some(ext => fileNameLower.endsWith(ext));
    if (!isAllowed) {
        alert('Please upload a PDF, TXT, or DOCX file only.');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    const dropzone = document.getElementById('dropzone');
    dropzone.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i><p>Uploading & Processing...</p>`;

    try {
        const res = await fetch(`${API_BASE}/documents/`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${currentToken}` },
            body: formData
        });
        
        if (res.ok) {
            const doc = await res.json();
            activeDocId = doc.id;
            activeConversationId = null;
            await loadDocuments();
            resetChatWorkspace();
        } else {
            const data = await res.json();
            alert(`Upload failed: ${data.detail || 'Unknown error'}`);
        }
    } catch (e) {
        alert('Upload server connection error.');
    } finally {
        dropzone.innerHTML = `
            <i class="fa-solid fa-cloud-arrow-up"></i>
            <p>Drag & Drop File here</p>
            <span>or click to browse</span>
        `;
    }
}

async function deleteDocument(id) {
    if (!confirm('Are you sure you want to delete this document and its chat history?')) return;
    try {
        const res = await fetch(`${API_BASE}/documents/${id}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${currentToken}` }
        });
        if (res.ok) {
            if (activeDocId === id) {
                activeDocId = null;
                activeConversationId = null;
                resetChatWorkspace();
            }
            loadDocuments();
        }
    } catch (e) {
        console.error(e);
    }
}

function selectDocument(id) {
    activeDocId = id;
    loadDocuments(); // Rerender list with active state highlight
    
    // Enable input elements
    document.getElementById('chat-input-box').removeAttribute('disabled');
    document.getElementById('chat-send-btn').removeAttribute('disabled');
    
    // Switch chat state to empty board
    activeConversationId = null;
    resetChatWorkspace();
    updateChatHeader();
}

// ================= RAG CHAT LOGIC ================= //
async function loadConversations() {
    try {
        const res = await fetch(`${API_BASE}/chat/conversations`, {
            headers: { 'Authorization': `Bearer ${currentToken}` }
        });
        if (!res.ok) return;
        const convs = await res.json();
        renderConversationsList(convs);
    } catch (e) {
        console.error(e);
    }
}

function renderConversationsList(convs) {
    const list = document.getElementById('conversations-list');
    list.innerHTML = '';
    
    convs.forEach(conv => {
        const li = document.createElement('li');
        li.className = `list-item ${activeConversationId === conv.id ? 'active' : ''}`;
        li.setAttribute('onclick', `selectConversation(${conv.id}, ${conv.document_id})`);
        
        li.innerHTML = `
            <div class="item-info">
                <i class="fa-regular fa-message"></i>
                <span title="${conv.title}">${conv.title}</span>
            </div>
            <button class="delete-item-btn" onclick="event.stopPropagation(); deleteConversation(${conv.id})">
                <i class="fa-regular fa-trash-can"></i>
            </button>
        `;
        list.appendChild(li);
    });
}

async function selectConversation(convId, docId) {
    activeConversationId = convId;
    activeDocId = docId;
    
    loadConversations();
    loadDocuments();
    
    document.getElementById('chat-input-box').removeAttribute('disabled');
    document.getElementById('chat-send-btn').removeAttribute('disabled');

    try {
        const res = await fetch(`${API_BASE}/chat/conversations/${convId}`, {
            headers: { 'Authorization': `Bearer ${currentToken}` }
        });
        if (!res.ok) return;
        const convDetail = await res.json();
        
        // Show active chat wrapper and clean message items
        document.getElementById('chat-content-wrapper').className = '';
        const container = document.getElementById('chat-messages-container');
        container.innerHTML = '';
        
        convDetail.messages.forEach(msg => {
            appendMessageBubble(msg.role, msg.content, msg.sources ? JSON.parse(msg.sources) : null);
        });
        scrollToBottom();
    } catch (e) {
        console.error(e);
    }
}

async function deleteConversation(id) {
    if (!confirm('Delete this conversation?')) return;
    try {
        const res = await fetch(`${API_BASE}/chat/conversations/${id}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${currentToken}` }
        });
        if (res.ok) {
            if (activeConversationId === id) {
                activeConversationId = null;
                resetChatWorkspace();
            }
            loadConversations();
        }
    } catch (e) {
        console.error(e);
    }
}

function resetChatWorkspace() {
    document.getElementById('chat-content-wrapper').className = 'empty-state';
    document.getElementById('chat-messages-container').innerHTML = '';
    document.getElementById('chat-input-box').value = '';
    document.getElementById('chat-input-box').style.height = 'auto';
    if (!activeDocId) {
        document.getElementById('chat-input-box').setAttribute('disabled', 'true');
        document.getElementById('chat-send-btn').setAttribute('disabled', 'true');
    }
    updateChatHeader();
}

function appendMessageBubble(role, text, sources = null) {
    const container = document.getElementById('chat-messages-container');
    const wrapper = document.getElementById('chat-content-wrapper');
    wrapper.className = ''; // Remove empty state display class
    
    const bubble = document.createElement('div');
    bubble.className = `message-bubble ${role}`;
    
    const initials = role === 'user' ? 'U' : 'DB';
    const avatarClass = role === 'user' ? 'user-avatar' : 'assistant-avatar';
    
    let sourceHtml = '';
    if (sources && sources.length > 0) {
        sourceHtml = `
            <div class="citation-panel">
                <span class="citation-title"><i class="fa-solid fa-book-open"></i> Sources:</span>
                ${sources.map(p => `<span class="citation-chip">Page ${p}</span>`).join('')}
            </div>
        `;
    }

    let loadingClass = '';
    if (role === 'assistant' && !text) {
        loadingClass = 'loading';
    }

    bubble.innerHTML = `
        <div class="bubble-avatar ${avatarClass}">${initials}</div>
        <div class="bubble-text-content ${loadingClass}">
            <div class="message-text"></div>
            ${sourceHtml}
        </div>
    `;
    
    const messageTextElem = bubble.querySelector('.message-text');
    if (role === 'assistant' && !text) {
        messageTextElem.innerHTML = `
            <div class="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
            </div>
        `;
    } else {
        messageTextElem.textContent = text.trim();
    }
    
    container.appendChild(bubble);
    return bubble;
}

// ================= STREAM READ CONSOLE LOGIC ================= //
async function handleChatSubmit(e) {
    e.preventDefault();
    const input = document.getElementById('chat-input-box');
    const questionText = input.value.trim();
    if (!questionText || !activeDocId) return;

    // Append User Question
    appendMessageBubble('user', questionText);
    input.value = '';
    input.style.height = 'auto';
    scrollToBottom();

    // Append AI response placeholder message bubble
    const aiBubble = appendMessageBubble('assistant', '');
    const textNode = aiBubble.querySelector('.message-text');
    const bubbleTextContent = aiBubble.querySelector('.bubble-text-content');
    
    // Disable inputs during streaming
    input.setAttribute('disabled', 'true');
    document.getElementById('chat-send-btn').setAttribute('disabled', 'true');

    try {
        const response = await fetch(`${API_BASE}/chat/ask`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${currentToken}`
            },
            body: JSON.stringify({
                question: questionText,
                document_id: activeDocId,
                conversation_id: activeConversationId || null
            })
        });

        if (!response.ok) {
            bubbleTextContent.classList.remove('loading');
            textNode.classList.remove('typing');
            textNode.textContent = "Error: Failed to fetch response from server.";
            input.removeAttribute('disabled');
            document.getElementById('chat-send-btn').removeAttribute('disabled');
            input.focus();
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let sourcesToRender = null;
        let currentEvent = null;
        let hasProcessedDataInEvent = false;

        // Smooth Typing Queue Setup
        let renderQueue = [];
        let renderTimer = null;
        let streamFinished = false;

        function finishMessage() {
            textNode.textContent = textNode.textContent.trim();
            textNode.classList.remove('typing');

            if (sourcesToRender && sourcesToRender.length > 0) {
                const citationDiv = document.createElement('div');
                citationDiv.className = 'citation-panel';
                citationDiv.innerHTML = `
                    <span class="citation-title"><i class="fa-solid fa-book-open"></i> Sources:</span>
                    ${sourcesToRender.map(p => `<span class="citation-chip">Page ${p}</span>`).join('')}
                `;
                bubbleTextContent.appendChild(citationDiv);
                scrollToBottomIfNeeded();
            }

            input.removeAttribute('disabled');
            document.getElementById('chat-send-btn').removeAttribute('disabled');
            input.focus();
        }

        function processRenderQueue() {
            if (renderQueue.length === 0) {
                if (streamFinished) {
                    finishMessage();
                } else {
                    renderTimer = null;
                }
                return;
            }

            // Dynamically speed up typing if the queue grows large
            let charsToRender = 1;
            if (renderQueue.length > 120) {
                charsToRender = 5;
            } else if (renderQueue.length > 60) {
                charsToRender = 3;
            } else if (renderQueue.length > 20) {
                charsToRender = 2;
            }

            let textToAppend = '';
            for (let i = 0; i < charsToRender; i++) {
                if (renderQueue.length > 0) {
                    textToAppend += renderQueue.shift();
                }
            }

            textNode.textContent += textToAppend;
            scrollToBottomIfNeeded();

            renderTimer = setTimeout(processRenderQueue, 15); // Smooth 15ms typing delay
        }

        function queueText(text) {
            for (const char of text) {
                renderQueue.push(char);
            }
            if (!renderTimer) {
                processRenderQueue();
            }
        }

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop(); // Keep partial line in buffer

            for (const line of lines) {
                // Remove trailing carriage return (\r) if present
                const cleanLine = line.endsWith('\r') ? line.slice(0, -1) : line;
                if (!cleanLine) continue;

                if (cleanLine.startsWith('event:')) {
                    currentEvent = cleanLine.slice(6).trim();
                    hasProcessedDataInEvent = false;
                } else if (cleanLine.startsWith('data:')) {
                    let dataStr = cleanLine;
                    if (dataStr.startsWith('data: ')) {
                        dataStr = dataStr.slice(6);
                    } else {
                        dataStr = dataStr.slice(5);
                    }
                    
                    if (currentEvent === 'metadata') {
                        const meta = JSON.parse(dataStr);
                        activeConversationId = meta.conversation_id;
                        sourcesToRender = meta.sources;
                        loadConversations(); // Reload sidebar to show title if new
                    } else if (currentEvent === 'chunk') {
                        if (bubbleTextContent.classList.contains('loading')) {
                            bubbleTextContent.classList.remove('loading');
                        }
                        if (!textNode.classList.contains('typing')) {
                            textNode.classList.add('typing');
                        }
                        
                        let chunkText = '';
                        if (hasProcessedDataInEvent) {
                            chunkText += '\n';
                        }
                        chunkText += dataStr;
                        queueText(chunkText);
                        hasProcessedDataInEvent = true;
                    } else if (currentEvent === 'error') {
                        if (bubbleTextContent.classList.contains('loading')) {
                            bubbleTextContent.classList.remove('loading');
                        }
                        textNode.classList.remove('typing');
                        textNode.textContent = "Error: " + dataStr;
                        input.removeAttribute('disabled');
                        document.getElementById('chat-send-btn').removeAttribute('disabled');
                        input.focus();
                        return;
                    }
                }
            }
        }

        // Stream completed
        streamFinished = true;
        if (renderQueue.length === 0 && !renderTimer) {
            finishMessage();
        }

    } catch (err) {
        bubbleTextContent.classList.remove('loading');
        textNode.classList.remove('typing');
        textNode.textContent = "Error: Lost server connection during stream.";
        input.removeAttribute('disabled');
        document.getElementById('chat-send-btn').removeAttribute('disabled');
        input.focus();
    }
}

function scrollToBottom() {
    const panel = document.getElementById('chat-content-wrapper');
    panel.scrollTop = panel.scrollHeight;
}

let scrollPending = false;
function scrollToBottomIfNeeded() {
    if (scrollPending) return;
    scrollPending = true;
    requestAnimationFrame(() => {
        const panel = document.getElementById('chat-content-wrapper');
        if (panel) {
            // Check if user is scrolled near the bottom (within 150px threshold)
            const isNearBottom = panel.scrollHeight - panel.scrollTop - panel.clientHeight < 150;
            if (isNearBottom) {
                panel.scrollTop = panel.scrollHeight;
            }
        }
        scrollPending = false;
    });
}


function updateChatHeader() {
    const header = document.getElementById('chat-header');
    if (!activeDocId) {
        header.style.display = 'none';
        return;
    }
    
    const doc = documentsCache.find(d => d.id === activeDocId);
    if (!doc) {
        header.style.display = 'none';
        return;
    }
    
    header.style.display = 'flex';
    document.getElementById('header-doc-title').textContent = doc.original_filename;
    
    // Set matching document format icon
    const icon = document.getElementById('header-doc-icon');
    icon.className = 'fa-solid';
    const filename = doc.original_filename.toLowerCase();
    if (filename.endsWith('.txt')) {
        icon.classList.add('fa-file-lines');
    } else if (filename.endsWith('.docx')) {
        icon.classList.add('fa-file-word');
    } else {
        icon.classList.add('fa-file-pdf');
    }

    // Load preview content automatically if panel is open
    const panel = document.getElementById('doc-preview-panel');
    if (panel && !panel.classList.contains('collapsed')) {
        loadPreviewContent();
    }
}

function startNewChat() {
    if (!activeDocId) return;
    activeConversationId = null;
    resetChatWorkspace();
}

function togglePreviewPanel() {
    if (!activeDocId) return;
    const panel = document.getElementById('doc-preview-panel');
    const toggleBtn = document.getElementById('toggle-preview-btn');
    
    if (panel.classList.contains('collapsed')) {
        panel.classList.remove('collapsed');
        toggleBtn.innerHTML = '<i class="fa-solid fa-eye-slash"></i> <span>Hide Document</span>';
        loadPreviewContent();
    } else {
        panel.classList.add('collapsed');
        toggleBtn.innerHTML = '<i class="fa-solid fa-eye"></i> <span>Show Document</span>';
    }
}

function loadPreviewContent() {
    if (!activeDocId) return;
    const doc = documentsCache.find(d => d.id === activeDocId);
    if (!doc) return;
    
    const iframe = document.getElementById('preview-iframe');
    const fallback = document.getElementById('preview-fallback');
    const headerTitle = document.getElementById('preview-header-title');
    const headerIcon = document.getElementById('preview-header-icon');
    const downloadLink = document.getElementById('download-link');
    
    // Set Header
    headerTitle.textContent = doc.original_filename;
    
    // Set Header Icon
    headerIcon.className = 'fa-solid';
    const filename = doc.original_filename.toLowerCase();
    let isPreviewable = true;
    
    if (filename.endsWith('.txt')) {
        headerIcon.classList.add('fa-file-lines');
    } else if (filename.endsWith('.docx')) {
        headerIcon.classList.add('fa-file-word');
        isPreviewable = false;
    } else {
        headerIcon.classList.add('fa-file-pdf');
    }
    
    // Set Download Links
    const previewUrl = `${API_BASE}/documents/${doc.id}/download?token=${currentToken}&disposition=inline`;
    const downloadUrl = `${API_BASE}/documents/${doc.id}/download?token=${currentToken}&disposition=attachment`;
    downloadLink.href = downloadUrl;
    
    if (isPreviewable) {
        fallback.style.display = 'none';
        iframe.style.display = 'block';
        iframe.src = previewUrl;
    } else {
        iframe.style.display = 'none';
        fallback.style.display = 'flex';
        
        // Update fallback message & button
        const fallbackIcon = document.getElementById('fallback-icon');
        fallbackIcon.className = 'fa-solid fa-file-word';
        document.getElementById('fallback-message').textContent = 
            `${doc.original_filename.split('.').pop().toUpperCase()} document preview is not supported directly in the browser.`;
        document.getElementById('fallback-download-btn').href = downloadUrl;
    }
}
