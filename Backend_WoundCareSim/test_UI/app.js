// Configuration
const API_BASE_URL = 'http://127.0.0.1:8000';
const WS_BASE_URL = API_BASE_URL.replace('http://', 'ws://').replace('https://', 'wss://');

// Global State
let currentSession = {
    sessionId: null,
    scenarioId: null,
    currentStep: null,
    nextStep: null,
    scenarioMetadata: null,
    mcqQuestions: [],
    actionCounter: 0,
    sessionToken: null,
    ws: null,
    wsConnected: false,
    lastSentEvent: '-',
    lastReceivedEvent: '-'
};

let mediaRecorder = null;
let recordedChunks = [];
let isRecording = false;
let mediaStream = null;
let activeRecordingTarget = null;
let pendingTranscriptionHandler = null;
let pendingStepTransition = null;
let feedbackRenderedForStep = false;

// ==========================================
// Utility Functions
// ==========================================

function showLoading() {
    document.getElementById('loadingSpinner').style.display = 'flex';
}

function hideLoading() {
    document.getElementById('loadingSpinner').style.display = 'none';
}

function showScreen(screenId) {
    // Hide all screens
    const screens = document.querySelectorAll('.screen');
    screens.forEach(screen => screen.style.display = 'none');
    
    // Show requested screen
    document.getElementById(screenId).style.display = 'block';
}

function showError(message) {
    alert('Error: ' + message);
}

function handleEnter(event, callback) {
    if (event.key === 'Enter') {
        callback();
    }
}

function updateRecordingUI(recording, buttonId, statusId, labelText) {
    const recordButton = document.getElementById(buttonId);
    const status = document.getElementById(statusId);
    if (!recordButton || !status) return;
    if (recording) {
        recordButton.classList.add('recording');
        recordButton.textContent = '⏹️ Stop Recording';
        status.textContent = 'Recording...';
    } else {
        recordButton.classList.remove('recording');
        recordButton.textContent = labelText;
        status.textContent = 'Not recording';
    }
}

function playAudioFromBase64(audioBase64, contentType = 'audio/mpeg') {
    if (!audioBase64) return Promise.resolve();
    const audio = new Audio(`data:${contentType};base64,${audioBase64}`);
    return new Promise(resolve => {
        audio.onended = resolve;
        audio.onerror = resolve;

        audio.play().catch(error => {
            console.error('Audio playback failed:', error);
            resolve();
        });
    });
}

async function apiCall(endpoint, method = 'GET', body = null) {
    showLoading();
    try {
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json'
            }
        };
        
        if (body) {
            options.body = JSON.stringify(body);
        }
        
        const response = await fetch(`${API_BASE_URL}${endpoint}`, options);
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'API request failed');
        }
        
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        showError(error.message);
        throw error;
    } finally {
        hideLoading();
    }
}

// ==========================================
// Session Management
// ==========================================

function updateDebugPanel() {
    const statusEl = document.getElementById('wsStatus');
    const sentEl = document.getElementById('lastSentEvent');
    const receivedEl = document.getElementById('lastReceivedEvent');
    if (!statusEl || !sentEl || !receivedEl) return;

    statusEl.textContent = currentSession.wsConnected ? 'Connected' : 'Disconnected';
    statusEl.className = currentSession.wsConnected ? 'debug-value connected' : 'debug-value disconnected';
    sentEl.textContent = currentSession.lastSentEvent || '-';
    receivedEl.textContent = currentSession.lastReceivedEvent || '-';
}

function getWebSocket() {
    if (currentSession.ws && currentSession.ws.readyState === WebSocket.OPEN) {
        return currentSession.ws;
    }
    return null;
}

function canUseWebSocket() {
    return !!getWebSocket();
}

function moveToNextStep(nextStep) {
    currentSession.nextStep = nextStep;
    continueToNextStep();
}

function handleTranscription(data) {
    const transcript = (data.text || '').trim();
    if (!transcript) return;

    const patientInput = document.getElementById('patientQuestion');
    const nurseInput = document.getElementById(getStaffNurseInputId());

    if (activeRecordingTarget?.targetType === 'patient' && patientInput) {
        patientInput.value = transcript;
    } else if (nurseInput) {
        nurseInput.value = transcript;
    }

    if (data.is_final && typeof pendingTranscriptionHandler === 'function') {
        pendingTranscriptionHandler(transcript);
        pendingTranscriptionHandler = null;
    }
}

function playAudio(base64Audio) {
    if (!base64Audio) return;
    const byteCharacters = atob(base64Audio);
    const byteNumbers = new Array(byteCharacters.length);

    for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
    }

    const byteArray = new Uint8Array(byteNumbers);
    const blob = new Blob([byteArray], { type: 'audio/wav' });
    const audioUrl = URL.createObjectURL(blob);

    const audio = new Audio(audioUrl);
    audio.play().catch((error) => {
        console.error('WebSocket audio playback failed:', error);
    }).finally(() => {
        setTimeout(() => URL.revokeObjectURL(audioUrl), 1000);
    });
}

function displayNurseMessage(text) {
    const responseId = getStaffNurseResponseId();
    const responseDiv = document.getElementById(responseId);
    if (!responseDiv) return;
    responseDiv.innerHTML = `
        <strong>Staff Nurse:</strong>
        <p>${text}</p>
    `;
}



function tryMoveToPendingStep() {
    if (pendingStepTransition && feedbackRenderedForStep) {
        moveToNextStep(pendingStepTransition);
        pendingStepTransition = null;
        feedbackRenderedForStep = false;
    }
}

function handleServerEvent(message) {
    if (message.type === 'error') {
        currentSession.lastReceivedEvent = `error: ${message.message}`;
        updateDebugPanel();
        console.error('WebSocket error event:', message.message);
        return;
    }

    const eventName = message.event || message.type || 'unknown';
    currentSession.lastReceivedEvent = eventName;
    updateDebugPanel();

    switch (message.event) {
        case 'transcription_result':
            handleTranscription(message.data || {});
            break;
        case 'tts_audio':
            playAudio((message.data || {}).audio_bytes);
            break;
        case 'real_time_feedback':
            displayRealtimeFeedback(message.data || {});
            break;
        case 'nurse_message':
            if ((message.data || {}).text) {
                const role = (message.data || {}).role;
                if (role === 'patient') {
                    addMessageToConversation('patient', message.data.text);
                } else {
                    displayNurseMessage(message.data.text);
                }
            }
            break;
        case 'final_feedback':
            displayHistoryFeedback(message.data || {}, null);
            feedbackRenderedForStep = true;
            tryMoveToPendingStep();
            break;
        case 'assessment_summary':
            displayAssessmentResults((message.data || {}).mcq_result || {}, null);
            feedbackRenderedForStep = true;
            tryMoveToPendingStep();
            break;
        case 'step_complete': {
            const nextStep = (message.data || {}).next_step;
            if (currentSession.currentStep === 'cleaning_and_dressing') {
                moveToNextStep(nextStep);
            } else if (feedbackRenderedForStep) {
                moveToNextStep(nextStep);
                feedbackRenderedForStep = false;
            } else {
                pendingStepTransition = nextStep;
            }
            break;
        }
        case 'session_end':
            showCompletionScreen();
            break;
        default:
            break;
    }
}

function sendWsEvent(event, data) {
    const ws = getWebSocket();
    if (!ws) return false;

    const payload = {
        type: 'event',
        event,
        data: data || {}
    };
    ws.send(JSON.stringify(payload));
    currentSession.lastSentEvent = event;
    updateDebugPanel();
    return true;
}

function connectWebSocket() {
    if (!currentSession.sessionId || !currentSession.sessionToken) return;

    if (currentSession.ws && [WebSocket.OPEN, WebSocket.CONNECTING].includes(currentSession.ws.readyState)) {
        return;
    }

    const wsUrl = `${WS_BASE_URL}/ws/session/${currentSession.sessionId}?token=${encodeURIComponent(currentSession.sessionToken)}`;
    const ws = new WebSocket(wsUrl);
    currentSession.ws = ws;

    ws.onopen = () => {
        currentSession.wsConnected = true;
        updateDebugPanel();
        console.log('WebSocket connected');
    };

    ws.onmessage = (event) => {
        try {
            handleServerEvent(JSON.parse(event.data));
        } catch (error) {
            console.error('Failed to parse WebSocket message:', error);
        }
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
        currentSession.wsConnected = false;
        updateDebugPanel();
        console.log('WebSocket disconnected');
    };
}

function disconnectWebSocket() {
    if (currentSession.ws) {
        currentSession.ws.close();
    }
    currentSession.ws = null;
    currentSession.wsConnected = false;
    updateDebugPanel();
}


async function startSession() {
    const scenarioId = document.getElementById('scenarioId').value.trim();
    const studentId = document.getElementById('studentId').value.trim();
    
    if (!scenarioId || !studentId) {
        showError('Please enter both Scenario ID and Student ID');
        return;
    }
    
    try {
        const response = await apiCall('/session/start', 'POST', {
            scenario_id: scenarioId,
            student_id: studentId
        });
        
        currentSession.sessionId = response.session_id;
        currentSession.scenarioId = scenarioId;
        currentSession.sessionToken = response.session_token || null;
        connectWebSocket();
        
        // Fetch session details
        await loadSessionInfo();
        
        // Start with HISTORY step
        showHistoryStep();
        
    } catch (error) {
        console.error('Failed to start session:', error);
    }
}

async function loadSessionInfo() {
    try {
        const session = await apiCall(`/session/${currentSession.sessionId}`);
        
        currentSession.currentStep = session.current_step;
        currentSession.scenarioMetadata = session.scenario_metadata;
        currentSession.mcqQuestions = session.scenario_metadata.assessment_questions || [];
        
        // Update UI
        document.getElementById('sessionInfo').style.display = 'flex';
        document.getElementById('sessionId').textContent = currentSession.sessionId;
        document.getElementById('currentStep').textContent = currentSession.currentStep;
        document.getElementById('scenarioTitle').textContent = session.scenario_metadata.title || 'Unknown';
        
    } catch (error) {
        console.error('Failed to load session info:', error);
    }
}

// ==========================================
// HISTORY Step
// ==========================================

function showHistoryStep() {
    currentSession.currentStep = 'history';
    showScreen('historyScreen');
    document.getElementById('currentStep').textContent = 'history';
    
    // Clear conversation box
    const conversationBox = document.getElementById('conversationBox');
    conversationBox.innerHTML = '<div class="conversation-empty">Start by asking the patient a question...</div>';

    const transcriptInput = document.getElementById('patientQuestion');
    if (transcriptInput) {
        transcriptInput.value = '';
    }
}

async function sendMessageText(message) {
    if (!message) {
        return;
    }

    try {
        addMessageToConversation('student', message);

        if (canUseWebSocket()) {
            const sent = sendWsEvent('text_message', { text: message });
            if (sent) {
                return;
            }
        }

        const response = await apiCall('/session/message', 'POST', {
            session_id: currentSession.sessionId,
            message: message
        });

        addMessageToConversation('patient', response.patient_response);

        if (response.patient_audio && response.patient_audio.audio_base64) {
            playAudioFromBase64(
                response.patient_audio.audio_base64,
                response.patient_audio.content_type
            );
        }

    } catch (error) {
        console.error('Failed to send message:', error);
    }
}

async function sendPatientMessage() {
    const input = document.getElementById('patientQuestion');
    if (!input) return;
    
    const message = input.value.trim();
    if (!message) return;
    
    // Send the message
    await sendMessageText(message);
    
    // Clear the input
    input.value = '';
}

async function togglePatientRecording() {
    if (isRecording) {
        stopRecording();
    } else {
        await startRecording({
            buttonId: 'recordButton',
            statusId: 'recordingStatus',
            labelText: '🎤 Record Voice',
            targetType: 'patient',
            onStop: async (blob) => {
                await sendAudioForTranscription(blob, async (transcript) => {
                    const input = document.getElementById('patientQuestion');
                    if (input) {
                        input.value = transcript;
                    }
                    await sendMessageText(transcript);
                });
            }
        });
    }
}

async function toggleNurseRecording() {
    if (isRecording) {
        stopRecording();
    } else {
        const recordingIds = getStaffNurseRecordingIds();
        if (!recordingIds) {
            showError('Voice recording is not available for this step.');
            return;
        }
        await startRecording({
            buttonId: recordingIds.buttonId,
            statusId: recordingIds.statusId,
            labelText: '🎤 Record Nurse Question',
            targetType: 'nurse',
            onStop: async (blob) => {
                await sendAudioForTranscription(blob, async (transcript) => {
                    const inputId = getStaffNurseInputId();
                    const input = document.getElementById(inputId);
                    if (input) {
                        input.value = transcript;
                    }
                    await askStaffNurse(transcript);
                });
            }
        });
    }
}

async function startRecording(target) {
    try {
        mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        recordedChunks = [];
        mediaRecorder = new MediaRecorder(mediaStream);
        activeRecordingTarget = target;
        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                recordedChunks.push(event.data);
            }
        };
        mediaRecorder.onstop = async () => {
            const blob = new Blob(recordedChunks, { type: mediaRecorder.mimeType || 'audio/webm' });
            recordedChunks = [];
            if (mediaStream) {
                mediaStream.getTracks().forEach(track => track.stop());
                mediaStream = null;
            }
            const recordingTarget = activeRecordingTarget;
            activeRecordingTarget = null;
            if (recordingTarget && typeof recordingTarget.onStop === 'function') {
                await recordingTarget.onStop(blob);
            }
        };
        mediaRecorder.start();
        isRecording = true;
        updateRecordingUI(true, target.buttonId, target.statusId, target.labelText);
    } catch (error) {
        console.error('Failed to start recording:', error);
        showError('Unable to access microphone. Please allow microphone access.');
    }
}



function blobToBase64(blob) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onloadend = () => {
            const result = reader.result || '';
            const base64 = String(result).split(',')[1] || '';
            resolve(base64);
        };
        reader.onerror = reject;
        reader.readAsDataURL(blob);
    });
}

function stopRecording() {
    if (mediaRecorder && isRecording) {
        mediaRecorder.stop();
        isRecording = false;
        if (activeRecordingTarget) {
            updateRecordingUI(
                false,
                activeRecordingTarget.buttonId,
                activeRecordingTarget.statusId,
                activeRecordingTarget.labelText
            );
        }
    }
}

async function sendAudioForTranscription(audioBlob, onTranscript) {
    showLoading();
    try {
        if (canUseWebSocket()) {
            const base64Audio = await blobToBase64(audioBlob);
            pendingTranscriptionHandler = onTranscript || null;
            sendWsEvent('stt_chunk', {
                audio_chunk: base64Audio
            });
            const sent = sendWsEvent('stt_complete', {
                filename: 'stream.webm',
                content_type: audioBlob.type || 'audio/webm'
            });
            if (sent) {
                return;
            }
            pendingTranscriptionHandler = null;
        }

        const formData = new FormData();
        formData.append('file', audioBlob, 'history-audio.webm');
        const response = await fetch(`${API_BASE_URL}/audio/stt`, {
            method: 'POST',
            body: formData
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'STT request failed');
        }
        const result = await response.json();
        const transcript = (result.text || '').trim();
        if (!transcript) {
            return;
        }
        if (onTranscript) {
            await onTranscript(transcript);
        }
    } catch (error) {
        console.error('Failed to transcribe audio:', error);
        showError(error.message);
    } finally {
        hideLoading();
    }
}

function addMessageToConversation(speaker, text) {
    const conversationBox = document.getElementById('conversationBox');
    
    // Remove empty state if present
    const emptyState = conversationBox.querySelector('.conversation-empty');
    if (emptyState) {
        emptyState.remove();
    }
    
    // Create message element
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${speaker}`;
    messageDiv.innerHTML = `
        <div class="message-speaker">${speaker === 'student' ? 'You' : 'Patient'}:</div>
        <div>${text}</div>
    `;
    
    conversationBox.appendChild(messageDiv);
    conversationBox.scrollTop = conversationBox.scrollHeight;
}

// ==========================================
// ASSESSMENT Step
// ==========================================

function showAssessmentStep() {
    currentSession.currentStep = 'assessment';
    showScreen('assessmentScreen');
    document.getElementById('currentStep').textContent = 'assessment';
    
    // Load MCQ questions
    loadMCQQuestions();
}

function loadMCQQuestions() {
    const container = document.getElementById('mcqContainer');
    container.innerHTML = '';
    
    if (!currentSession.mcqQuestions || currentSession.mcqQuestions.length === 0) {
        container.innerHTML = '<p class="text-muted">No assessment questions available.</p>';
        return;
    }
    
    currentSession.mcqQuestions.forEach((question, index) => {
        const questionDiv = document.createElement('div');
        questionDiv.className = 'mcq-question';
        questionDiv.id = `mcq-${question.id}`;
        
        questionDiv.innerHTML = `
            <div class="mcq-header">
                <span class="question-number">Question ${index + 1} of ${currentSession.mcqQuestions.length}</span>
                <span class="mcq-status" id="status-${question.id}" style="display: none;"></span>
            </div>
            <div class="question-text">${question.question}</div>
            <div class="mcq-options" id="options-${question.id}">
                ${question.options.map(option => `
                    <div class="mcq-option" onclick="selectMCQOption('${question.id}', '${option}')">
                        ${option}
                    </div>
                `).join('')}
            </div>
            <div class="mcq-feedback" id="feedback-${question.id}" style="display: none;"></div>
        `;
        
        container.appendChild(questionDiv);
    });
}

async function selectMCQOption(questionId, answer) {
    try {
        if (canUseWebSocket()) {
            sendWsEvent('mcq_answer', {
                question_id: questionId,
                answer: answer
            });
        }

        // Submit answer
        const response = await apiCall('/session/mcq-answer', 'POST', {
            session_id: currentSession.sessionId,
            question_id: questionId,
            answer: answer
        });
        
        // Update UI with immediate feedback
        const statusBadge = document.getElementById(`status-${questionId}`);
        const feedbackDiv = document.getElementById(`feedback-${questionId}`);
        const optionsDiv = document.getElementById(`options-${questionId}`);
        
        // Show status
        statusBadge.style.display = 'inline-block';
        statusBadge.className = `mcq-status ${response.status}`;
        statusBadge.textContent = response.is_correct ? '✓ Correct' : '✗ Incorrect';
        
        // Show explanation
        feedbackDiv.style.display = 'block';
        feedbackDiv.className = `mcq-feedback ${response.status}`;
        feedbackDiv.innerHTML = `<strong>Explanation:</strong> ${response.explanation}`;
        
        // Disable options
        optionsDiv.style.pointerEvents = 'none';
        optionsDiv.style.opacity = '0.6';

        if (response.feedback_audio && response.feedback_audio.audio_base64) {
            playAudioFromBase64(
                response.feedback_audio.audio_base64,
                response.feedback_audio.content_type
            );
        }
        
    } catch (error) {
        console.error('Failed to submit MCQ answer:', error);
    }
}

// ==========================================
// CLEANING AND DRESSING Step (Combined - 9 Actions)
// ==========================================

function showCleaningAndDressingStep() {
    currentSession.currentStep = 'cleaning_and_dressing';
    currentSession.actionCounter = 0;
    showScreen('cleaningAndDressingScreen');
    document.getElementById('currentStep').textContent = 'cleaning_and_dressing';
    
    // Reset counter
    document.getElementById('actionCounter').textContent = '0';
    
    // Load action buttons
    loadCleaningAndDressingActions();
    
    // Clear feedback
    const feedbackBox = document.getElementById('realtimeFeedback');
    feedbackBox.innerHTML = '<strong>Real-Time Feedback:</strong><p class="text-muted">Perform actions to receive feedback...</p>';
}

function loadCleaningAndDressingActions() {
    // ⭐ FIX #2: Match action names with RAG guidelines exactly
    const actions = [
        { type: 'action_initial_hand_hygiene', label: '1. Initial Hand Hygiene' },
        { type: 'action_clean_trolley', label: '2. Clean the Dressing Trolley' },
        { type: 'action_hand_hygiene_after_cleaning', label: '3. Hand Hygiene After Trolley Cleaning' },
        { type: 'action_select_solution', label: '4. Select Prescribed Cleaning Solution' },
        // Action 5 is verification - handled by conversational chat
        { type: 'action_select_dressing', label: '6. Select Dressing Materials' },
        // Action 7 is verification - handled by conversational chat
        { type: 'action_arrange_materials', label: '8. Arrange Solutions and Materials on Trolley' },
        { type: 'action_bring_trolley', label: '9. Bring Prepared Trolley to Patient Area' }
    ];
    
    const container = document.getElementById('cleaningAndDressingActions');
    container.innerHTML = '';
    
    actions.forEach(action => {
        const button = document.createElement('button');
        button.className = 'action-btn';
        button.onclick = () => recordAction(action.type);
        button.innerHTML = `
            <span class="checkmark">✓</span>
            <span>${action.label}</span>
        `;
        container.appendChild(button);
    });
}

async function recordAction(actionType) {
    try {
        if (canUseWebSocket()) {
            const sent = sendWsEvent('action_performed', {
                action_type: actionType
            });
            if (sent) return;
        }

        const response = await apiCall('/session/action', 'POST', {
            session_id: currentSession.sessionId,
            action_type: actionType
        });
        
        // ⭐ FIX #1: Handle duplicate actions
        if (response.already_performed) {
            // Show duplicate action notification
            displayRealtimeFeedback({
                message: response.feedback.message,
                status: 'duplicate',
                can_proceed: true,
                missing_actions: []
            }, response.feedback_audio);
            return; // Don't increment counter or update UI
        }
        
        // Update counter (only if action was actually recorded)
        if (response.action_recorded) {
            currentSession.actionCounter++;
            document.getElementById('actionCounter').textContent = currentSession.actionCounter;
        }
        
        // Display real-time feedback
        displayRealtimeFeedback(response.feedback, response.feedback_audio);
        
    } catch (error) {
        console.error('Failed to record action:', error);
    }
}

// Verification is now handled automatically in askStaffNurse()
// No separate functions needed

function displayRealtimeFeedback(feedback, feedbackAudio) {
    const feedbackBox = document.getElementById('realtimeFeedback');
    
    // ⭐ NEW: Handle duplicate action status
    let statusClass = 'success';
    let statusIcon = '✓';
    
    if (feedback.status === 'complete') {
        statusClass = 'success';
        statusIcon = '✓';
    } else if (feedback.status === 'missing_prerequisites') {
        statusClass = 'warning';
        statusIcon = '⚠️';
    } else if (feedback.status === 'duplicate') {
        statusClass = 'info';
        statusIcon = 'ℹ️';
    }
    
    let html = `
        <strong>Real-Time Feedback:</strong>
        <div class="feedback-message ${statusClass}">
            <span class="feedback-icon">${statusIcon}</span>
            <p>${feedback.message}</p>
    `;
    
    // Show missing actions if any
    if (feedback.missing_actions && feedback.missing_actions.length > 0) {
        html += `
            <div class="missing-actions">
                <strong>Missing Prerequisites:</strong>
                <ul>
                    ${feedback.missing_actions.map(action => `
                        <li>${action.replace('action_', '').replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</li>
                    `).join('')}
                </ul>
            </div>
        `;
    }
    
    html += '</div>';
    feedbackBox.innerHTML = html;

    if (feedbackAudio && feedbackAudio.audio_base64) {
        playAudioFromBase64(feedbackAudio.audio_base64, feedbackAudio.content_type);
    }
}

// ==========================================
// Staff Nurse
// ==========================================

function getStaffNurseInputId() {
    const step = currentSession.currentStep;
    if (step === 'history') {
        return 'nurseQuestionHistory';
    }
    if (step === 'assessment') {
        return 'nurseQuestionAssessment';
    }
    return 'nurseQuestionCleaningAndDressing';
}

function getStaffNurseResponseId() {
    const step = currentSession.currentStep;
    if (step === 'history') {
        return 'staffNurseHistory';
    }
    if (step === 'assessment') {
        return 'staffNurseAssessment';
    }
    return 'staffNurseCleaningAndDressing';
}

function getStaffNurseRecordingIds() {
    const step = currentSession.currentStep;
    if (step === 'history') {
        return { buttonId: 'nurseRecordButton', statusId: 'nurseRecordingStatus' };
    }
    if (step === 'cleaning_and_dressing') {
        return { buttonId: 'nurseRecordButtonCleaning', statusId: 'nurseRecordingStatusCleaning' };
    }
    return null;
}

async function askStaffNurse(messageOverride) {
    const inputId = getStaffNurseInputId();
    const responseId = getStaffNurseResponseId();
    
    const input = document.getElementById(inputId);
    const message = messageOverride ? messageOverride.trim() : input.value.trim();
    
    if (!message) return;
    
    try {
        if (canUseWebSocket() && currentSession.currentStep !== 'history') {
            const sent = sendWsEvent('text_message', { text: message });
            if (sent) {
                input.value = '';
                return;
            }
        }

        const response = await apiCall('/session/staff-nurse', 'POST', {
            session_id: currentSession.sessionId,
            message: message
        });
        
        // ⭐ NEW: Handle auto-detected verification
        const responseDiv = document.getElementById(responseId);
        
        if (response.is_verification && response.action_recorded) {
            // This was a verification request - recorded as action
            responseDiv.innerHTML = `
                <div class="verification-response">
                    <strong>Staff Nurse (Verification - Action Recorded):</strong>
                    <p>${response.staff_nurse_response}</p>
                </div>
            `;
            
            // Update counter
            currentSession.actionCounter++;
            document.getElementById('actionCounter').textContent = currentSession.actionCounter;
            
            // Display real-time feedback
            if (response.feedback) {
                displayRealtimeFeedback(response.feedback, null);
            }
        } else if (response.is_verification && response.already_performed) {
            // Verification already done
            responseDiv.innerHTML = `
                <div class="info-message">
                    <strong>Staff Nurse:</strong>
                    <p>${response.staff_nurse_response}</p>
                </div>
            `;
        } else {
            // Regular guidance
            responseDiv.innerHTML = `
                <strong>Staff Nurse (Guidance):</strong>
                <p>${response.staff_nurse_response}</p>
            `;
        }

        if (response.is_verification && response.action_recorded) {
            if (response.staff_nurse_audio && response.staff_nurse_audio.audio_base64) {
                await playAudioFromBase64(
                    response.staff_nurse_audio.audio_base64,
                    response.staff_nurse_audio.content_type
                );
            }

            if (response.feedback_audio && response.feedback_audio.audio_base64) {
                await playAudioFromBase64(
                    response.feedback_audio.audio_base64,
                    response.feedback_audio.content_type
                );
            }
        } else if (response.staff_nurse_audio && response.staff_nurse_audio.audio_base64) {
            playAudioFromBase64(
                response.staff_nurse_audio.audio_base64,
                response.staff_nurse_audio.content_type
            );
        }
        
        input.value = '';
        
    } catch (error) {
        console.error('Failed to ask staff nurse:', error);
    }
}

// ==========================================
// Step Completion
// ==========================================

async function finishStep(step) {
    try {
        if (canUseWebSocket()) {
            if (step === 'history' || step === 'assessment') {
                feedbackRenderedForStep = false;
                pendingStepTransition = null;
            }
            const sent = sendWsEvent('step_complete', { step });
            if (sent) return;
        }

        const response = await apiCall('/session/step', 'POST', {
            session_id: currentSession.sessionId,
            step: step
        });
        
        // Store next step
        currentSession.nextStep = response.next_step;
        
        // Display appropriate feedback/results
        if (step === 'history') {
            // History: Show narrated feedback + score
            displayHistoryFeedback(response.feedback, response.feedback_audio);
        } else if (step === 'assessment') {
            // Assessment: Show MCQ results only (no narration)
            displayAssessmentResults(response.mcq_result, response.summary_audio);
        } else if (step === 'cleaning_and_dressing') {
            // Cleaning & Dressing: Silently move to next step with no summary/modal/audio
            continueToNextStep();
        }
        
    } catch (error) {
        console.error('Failed to finish step:', error);
    }
}

function displayHistoryFeedback(feedback, feedbackAudio) {
    const modal = document.getElementById('feedbackModal');
    const content = document.getElementById('feedbackContent');
    
    let html = `
        <div class="feedback-section">
            <h3>📋 History Taking Feedback</h3>
    `;
    
    // Narrated feedback (primary)
    if (feedback.narrated_feedback) {
        html += `
            <div class="narrated-feedback">
                ${feedback.narrated_feedback.message_text}
            </div>
        `;
    }
    
    // Score display
    if (feedback.score !== undefined) {
        const scorePercent = (feedback.score * 100).toFixed(0);
        html += `
            <div class="score-display">
                <div class="score-label">Step Quality Score</div>
                <div class="score-value">${feedback.score.toFixed(2)}</div>
                <div class="score-bar">
                    <div class="score-fill" style="width: ${scorePercent}%"></div>
                </div>
                <div class="score-interpretation">${feedback.interpretation || ''}</div>
            </div>
        `;
    }
    
    html += '</div>';
    
    content.innerHTML = html;
    modal.style.display = 'flex';

    if (feedbackAudio && feedbackAudio.audio_base64) {
        playAudioFromBase64(feedbackAudio.audio_base64, feedbackAudio.content_type);
    }
}

function displayAssessmentResults(mcqResult, summaryAudio) {
    if (!mcqResult || mcqResult.score === undefined) {
        return;
    }

    const modal = document.getElementById('feedbackModal');
    const content = document.getElementById('feedbackContent');
    
    const scorePercent = (mcqResult.score * 100).toFixed(0);
    
    let html = `
        <div class="feedback-section">
            <h3>📊 Assessment Results</h3>
            <div class="mcq-summary">
                <div class="mcq-score-large">
                    ${mcqResult.correct_count} / ${mcqResult.total_questions}
                </div>
                <div class="mcq-summary-text">
                    ${mcqResult.summary}
                </div>
                <div class="score-bar">
                    <div class="score-fill" style="width: ${scorePercent}%"></div>
                </div>
            </div>
    `;
    
    // Note: No narrated feedback for assessment - MCQ explanations already provided
    html += `
            <div class="info-box">
                <strong>ℹ️ Note:</strong> Detailed explanations were provided for each question during the assessment.
            </div>
        </div>
    `;
    
    content.innerHTML = html;
    modal.style.display = 'flex';

    if (summaryAudio && summaryAudio.audio_base64) {
        playAudioFromBase64(summaryAudio.audio_base64, summaryAudio.content_type);
    }
}

function displayPreparationSummary(summary) {
    const modal = document.getElementById('feedbackModal');
    const content = document.getElementById('feedbackContent');
    
    let html = `
        <div class="feedback-section">
            <h3>🔧 Preparation Summary</h3>
            <div class="preparation-summary">
                <p>${summary.message}</p>
                <div class="action-count">
                    <strong>Actions Completed:</strong> ${summary.actions_completed} / ${summary.expected_actions}
                </div>
            </div>
            <div class="info-box">
                <strong>ℹ️ Note:</strong> Real-time feedback was provided during preparation. No final score is given for this step.
            </div>
        </div>
    `;
    
    content.innerHTML = html;
    modal.style.display = 'flex';
}

function closeFeedbackModal() {
    document.getElementById('feedbackModal').style.display = 'none';
}

function continueToNextStep() {
    closeFeedbackModal();
    
    // Navigate to next step
    switch (currentSession.nextStep) {
        case 'assessment':
            showAssessmentStep();
            break;
        case 'cleaning_and_dressing':
            showCleaningAndDressingStep();
            break;
        case 'completed':
            showCompletionScreen();
            break;
        default:
            console.error('Unknown next step:', currentSession.nextStep);
    }
}

// ==========================================
// Completion Screen
// ==========================================

function showCompletionScreen() {
    currentSession.currentStep = 'completed';
    showScreen('completionScreen');
    document.getElementById('currentStep').textContent = 'completed';
    
    const summary = document.getElementById('completionSummary');
    summary.innerHTML = `
        <h3>Session Summary</h3>
        <p><strong>Session ID:</strong> ${currentSession.sessionId}</p>
        <p><strong>Scenario:</strong> ${currentSession.scenarioMetadata.title}</p>
        <div class="completion-message">
            <p>✓ Patient History Completed</p>
            <p>✓ Wound Assessment Completed</p>
            <p>✓ Cleaning & Dressing Preparation Completed</p>
        </div>
        <p class="success-message">All procedural steps have been completed successfully!</p>
    `;
}

// ==========================================
// Initialize
// ==========================================

document.addEventListener('DOMContentLoaded', () => {
    console.log('VR Nursing Education System - Test UI Loaded (Updated)');
    showScreen('startScreen');
    updateDebugPanel();
});

window.addEventListener('beforeunload', () => {
    disconnectWebSocket();
});
