// Configuration
const API_BASE_URL = 'http://127.0.0.1:8000';

// Global State
let currentSession = {
    sessionId: null,
    scenarioId: null,
    currentStep: null,
    nextStep: null,
    scenarioMetadata: null,
    mcqQuestions: [],
    actionCounter: 0
};

let voiceRecorder = null;
let audioPlayer = null;
let feedbackAudio = null;
let voiceControlsInitialized = false;

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

async function apiCallFormData(endpoint, formData) {
    showLoading();
    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, {
            method: 'POST',
            body: formData
        });

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
// Voice Utilities
// ==========================================

class VoiceRecorder {
    constructor(button, statusEl, waveformEl, fallbackEl) {
        this.button = button;
        this.statusEl = statusEl;
        this.waveformEl = waveformEl;
        this.fallbackEl = fallbackEl;
        this.mediaRecorder = null;
        this.chunks = [];
        this.stream = null;
        this.isRecording = false;
    }

    async init() {
        if (!navigator.mediaDevices || !window.MediaRecorder) {
            this.showFallback('Voice recording not supported in this browser.');
            return;
        }
        this.statusEl.textContent = 'Ready to record';
    }

    showFallback(message) {
        this.statusEl.textContent = message;
        this.fallbackEl.style.display = 'flex';
    }

    async start() {
        if (this.isRecording) return;
        try {
            if (!this.stream) {
                this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            }
            this.chunks = [];
            this.mediaRecorder = new MediaRecorder(this.stream);
            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    this.chunks.push(event.data);
                }
            };
            this.mediaRecorder.start();
            this.isRecording = true;
            this.button.classList.add('recording');
            this.statusEl.textContent = 'Recording... release to send';
            this.waveformEl.classList.add('active');
        } catch (error) {
            console.error('Recording error:', error);
            this.showFallback('Microphone access failed. Use text input instead.');
        }
    }

    async stop() {
        if (!this.isRecording || !this.mediaRecorder) return null;
        return new Promise((resolve) => {
            this.mediaRecorder.onstop = () => {
                const blob = new Blob(this.chunks, { type: this.mediaRecorder.mimeType });
                this.isRecording = false;
                this.button.classList.remove('recording');
                this.statusEl.textContent = 'Transcribing...';
                this.waveformEl.classList.remove('active');
                resolve(blob);
            };
            this.mediaRecorder.stop();
        });
    }
}

class AudioPlayer {
    constructor() {
        this.activeAudio = null;
        this.activeIndicator = null;
    }

    playBase64(base64, indicatorEl) {
        if (!base64) return;
        const audio = new Audio(`data:audio/mpeg;base64,${base64}`);
        this.stop();
        this.activeAudio = audio;
        this.activeIndicator = indicatorEl;
        if (indicatorEl) {
            indicatorEl.classList.add('playing');
        }
        audio.play().catch((error) => {
            console.error('Audio playback error:', error);
            if (indicatorEl) {
                indicatorEl.classList.remove('playing');
            }
        });
        audio.onended = () => {
            if (indicatorEl) {
                indicatorEl.classList.remove('playing');
            }
        };
    }

    stop() {
        if (this.activeAudio) {
            this.activeAudio.pause();
            this.activeAudio.currentTime = 0;
            if (this.activeIndicator) {
                this.activeIndicator.classList.remove('playing');
            }
        }
    }
}

// ==========================================
// Session Management
// ==========================================

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

    initializeVoiceControls();
}

async function sendMessage(messageOverride = null, options = {}) {
    const input = document.getElementById('patientQuestion');
    const message = messageOverride || input?.value.trim();
    const voiceMode = options.voiceMode || false;
    const addStudent = options.addStudent !== false;

    if (!message) return;

    try {
        if (addStudent) {
            addMessageToConversation('student', message);
        }
        if (input) {
            input.value = '';
        }

        const response = await apiCall('/session/message', 'POST', {
            session_id: currentSession.sessionId,
            message: message,
            voice_mode: voiceMode
        });

        const patientMessage = addMessageToConversation('patient', response.patient_response, response.audio_base64);
        if (response.audio_base64) {
            audioPlayer.playBase64(response.audio_base64, patientMessage.indicator);
        }
    } catch (error) {
        console.error('Failed to send message:', error);
    }
}

function addMessageToConversation(speaker, text, audioBase64 = null) {
    const conversationBox = document.getElementById('conversationBox');
    
    // Remove empty state if present
    const emptyState = conversationBox.querySelector('.conversation-empty');
    if (emptyState) {
        emptyState.remove();
    }
    
    // Create message element
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${speaker}`;
    const speakerLabel = speaker === 'student' ? 'You' : 'Patient';
    const audioIndicator = audioBase64
        ? `
            <span class="audio-indicator">
                <span class="speaker-icon">🔊</span>
                <span class="bars">
                    <span></span><span></span><span></span>
                </span>
                <span class="audio-text">Playing</span>
            </span>
        `
        : '';

    messageDiv.innerHTML = `
        <div class="message-speaker">${speakerLabel}:${audioIndicator}</div>
        <div>${text}</div>
    `;
    
    conversationBox.appendChild(messageDiv);
    conversationBox.scrollTop = conversationBox.scrollHeight;

    return {
        element: messageDiv,
        indicator: messageDiv.querySelector('.audio-indicator')
    };
}

async function initializeVoiceControls() {
    if (voiceControlsInitialized) return;
    const button = document.getElementById('holdToSpeakButton');
    const statusEl = document.getElementById('voiceStatus');
    const waveformEl = document.getElementById('voiceWaveform');
    const fallbackEl = document.getElementById('voiceFallback');

    if (!button || !statusEl || !waveformEl || !fallbackEl) return;

    voiceRecorder = new VoiceRecorder(button, statusEl, waveformEl, fallbackEl);
    audioPlayer = new AudioPlayer();
    await voiceRecorder.init();

    const stopAndSend = async () => {
        const blob = await voiceRecorder.stop();
        if (!blob) return;
        try {
            const formData = new FormData();
            formData.append('file', blob, 'history-recording.webm');
            const result = await apiCallFormData('/voice/transcribe', formData);
            statusEl.textContent = 'Ready to record';
            await sendMessage(result.text, { voiceMode: true });
        } catch (error) {
            statusEl.textContent = 'Transcription failed. Use text input.';
            fallbackEl.style.display = 'flex';
        }
    };

    button.addEventListener('pointerdown', async (event) => {
        event.preventDefault();
        await voiceRecorder.start();
    });

    button.addEventListener('pointerup', async (event) => {
        event.preventDefault();
        await stopAndSend();
    });

    button.addEventListener('pointerleave', async () => {
        if (voiceRecorder.isRecording) {
            await stopAndSend();
        }
    });

    button.addEventListener('pointercancel', async () => {
        if (voiceRecorder.isRecording) {
            await stopAndSend();
        }
    });

    voiceControlsInitialized = true;
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
            });
            return; // Don't increment counter or update UI
        }
        
        // Update counter (only if action was actually recorded)
        if (response.action_recorded) {
            currentSession.actionCounter++;
            document.getElementById('actionCounter').textContent = currentSession.actionCounter;
        }
        
        // Display real-time feedback
        displayRealtimeFeedback(response.feedback);
        
    } catch (error) {
        console.error('Failed to record action:', error);
    }
}

// Verification is now handled automatically in askStaffNurse()
// No separate functions needed

function displayRealtimeFeedback(feedback) {
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
}

// ==========================================
// Staff Nurse
// ==========================================

async function askStaffNurse() {
    const step = currentSession.currentStep;
    let inputId, responseId;
    
    // Determine input/response IDs based on step
    if (step === 'history') {
        inputId = 'nurseQuestionHistory';
        responseId = 'staffNurseHistory';
    } else if (step === 'assessment') {
        inputId = 'nurseQuestionAssessment';
        responseId = 'staffNurseAssessment';
    } else if (step === 'cleaning_and_dressing') {
        inputId = 'nurseQuestionCleaningAndDressing';
        responseId = 'staffNurseCleaningAndDressing';
    }
    
    const input = document.getElementById(inputId);
    const message = input.value.trim();
    
    if (!message) return;
    
    try {
        const audioIndicator = (response) => response.audio_base64
            ? `
                <span class="audio-indicator">
                    <span class="speaker-icon">🔊</span>
                    <span class="bars">
                        <span></span><span></span><span></span>
                    </span>
                    <span class="audio-text">Playing</span>
                </span>
            `
            : '';

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
                    ${audioIndicator(response)}
                    <p>${response.staff_nurse_response}</p>
                </div>
            `;
            
            // Update counter
            currentSession.actionCounter++;
            document.getElementById('actionCounter').textContent = currentSession.actionCounter;
            
            // Display real-time feedback
            if (response.feedback) {
                displayRealtimeFeedback(response.feedback);
            }
        } else if (response.is_verification && response.already_performed) {
            // Verification already done
            responseDiv.innerHTML = `
                <div class="info-message">
                    <strong>Staff Nurse:</strong>
                    ${audioIndicator(response)}
                    <p>${response.staff_nurse_response}</p>
                </div>
            `;
        } else {
            // Regular guidance
            responseDiv.innerHTML = `
                <strong>Staff Nurse (Guidance):</strong>
                ${audioIndicator(response)}
                <p>${response.staff_nurse_response}</p>
            `;
        }

        if (response.audio_base64) {
            const indicator = responseDiv.querySelector('.audio-indicator');
            if (indicator) {
                audioPlayer.playBase64(response.audio_base64, indicator);
            }
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
        const response = await apiCall('/session/step', 'POST', {
            session_id: currentSession.sessionId,
            step: step
        });
        
        // Store next step
        currentSession.nextStep = response.next_step;
        
        // Display appropriate feedback/results
        if (step === 'history') {
            // History: Show narrated feedback + score
            displayHistoryFeedback(response.feedback);
        } else if (step === 'assessment') {
            // Assessment: Show MCQ results only (no narration)
            displayAssessmentResults(response.mcq_result);
        } else if (step === 'cleaning_and_dressing') {
            // Cleaning & Dressing: Show summary only (no scores/narration)
            displayPreparationSummary(response.summary);
        }
        
    } catch (error) {
        console.error('Failed to finish step:', error);
    }
}

function displayHistoryFeedback(feedback) {
    const modal = document.getElementById('feedbackModal');
    const content = document.getElementById('feedbackContent');
    const audioControls = document.getElementById('feedbackAudioControls');
    
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

    if (feedback.narrated_feedback?.message_text) {
        playFeedbackNarration(feedback.narrated_feedback.message_text);
        audioControls.style.display = 'flex';
    } else {
        audioControls.style.display = 'none';
    }
}

function displayAssessmentResults(mcqResult) {
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
    if (feedbackAudio) {
        feedbackAudio.pause();
        feedbackAudio = null;
    }
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
    if (!audioPlayer) {
        audioPlayer = new AudioPlayer();
    }
    showScreen('startScreen');
});

async function playFeedbackNarration(text) {
    try {
        const response = await fetch(`${API_BASE_URL}/voice/synthesize`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ text })
        });

        if (!response.ok) {
            throw new Error('Failed to synthesize feedback');
        }

        const blob = await response.blob();
        if (feedbackAudio) {
            feedbackAudio.pause();
        }
        feedbackAudio = new Audio(URL.createObjectURL(blob));
        feedbackAudio.play().catch((error) => console.error('Feedback audio play failed:', error));
    } catch (error) {
        console.error('Feedback narration error:', error);
    }
}

function toggleFeedbackAudio() {
    if (!feedbackAudio) return;
    const toggleButton = document.getElementById('feedbackAudioToggle');
    if (feedbackAudio.paused) {
        feedbackAudio.play().catch((error) => console.error('Feedback audio play failed:', error));
        toggleButton.textContent = '⏸ Pause';
    } else {
        feedbackAudio.pause();
        toggleButton.textContent = '▶️ Play';
    }
}

function replayFeedbackAudio() {
    if (!feedbackAudio) return;
    feedbackAudio.currentTime = 0;
    feedbackAudio.play().catch((error) => console.error('Feedback audio play failed:', error));
    document.getElementById('feedbackAudioToggle').textContent = '⏸ Pause';
}
