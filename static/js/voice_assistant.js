/**
 * Voice Assistant for Campus Maintenance Tracker
 * Uses browser Web Speech API (SpeechRecognition / webkitSpeechRecognition)
 * Converts voice into text, parses location, category, priority, and auto-fills the form.
 */

document.addEventListener('DOMContentLoaded', () => {
  const micBtn = document.getElementById('micBtn');
  const voiceStatus = document.getElementById('voiceStatus');
  const liveTranscript = document.getElementById('liveTranscript');
  const speechSupportAlert = document.getElementById('speechSupportAlert');

  // Form input targets
  const titleInput = document.getElementById('complaintTitle');
  const descInput = document.getElementById('complaintDesc');
  const locationInput = document.getElementById('complaintLocation');
  const categorySelect = document.getElementById('complaintCategory');
  const prioritySelect = document.getElementById('complaintPriority');
  const isVoiceHidden = document.getElementById('isVoiceSubmitted');
  const troubleshootingContainer = document.getElementById('troubleshootingContainer');
  const troubleshootingText = document.getElementById('troubleshootingText');

  // Check browser Web Speech API support
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

  if (!SpeechRecognition) {
    if (speechSupportAlert) {
      speechSupportAlert.style.display = 'block';
      speechSupportAlert.innerHTML = `
        <strong>Note:</strong> Browser speech recognition is not supported in your current browser.
        You can still conveniently type your complaint details in the form below.
      `;
    }
    if (micBtn) {
      micBtn.disabled = true;
      micBtn.title = "Speech recognition unavailable in this browser";
      micBtn.style.opacity = '0.6';
    }
    return;
  }

  let recognition = new SpeechRecognition();
  recognition.continuous = false;
  recognition.interimResults = true;
  recognition.lang = 'en-US';

  let isListening = false;
  let finalTranscript = '';

  micBtn.addEventListener('click', () => {
    if (isListening) {
      recognition.stop();
    } else {
      try {
        finalTranscript = '';
        recognition.start();
      } catch (err) {
        console.error("Speech start error:", err);
      }
    }
  });

  recognition.onstart = () => {
    isListening = true;
    micBtn.classList.add('listening');
    voiceStatus.textContent = "Listening... Speak now";
    voiceStatus.style.color = '#ea580c';
    if (liveTranscript) {
      liveTranscript.style.display = 'block';
      liveTranscript.textContent = "Listening to audio input...";
    }
  };

  recognition.onresult = (event) => {
    let interim = '';
    for (let i = event.resultIndex; i < event.results.length; ++i) {
      if (event.results[i].isFinal) {
        finalTranscript += event.results[i][0].transcript;
      } else {
        interim += event.results[i][0].transcript;
      }
    }
    liveTranscript.textContent = finalTranscript || interim || "Listening...";
  };

  recognition.onerror = (event) => {
    console.warn("Speech recognition error:", event.error);
    isListening = false;
    micBtn.classList.remove('listening');
    if (event.error === 'not-allowed') {
      voiceStatus.textContent = "Microphone access was denied. Please allow microphone permissions or type below.";
    } else if (event.error === 'no-speech') {
      voiceStatus.textContent = "No speech detected. Click the mic icon to try again.";
    } else {
      voiceStatus.textContent = `Speech error (${event.error}). Please try again or type manually.`;
    }
    voiceStatus.style.color = '#fee2e2';
  };

  recognition.onend = () => {
    isListening = false;
    micBtn.classList.remove('listening');

    if (finalTranscript.trim()) {
      voiceStatus.textContent = "Processing speech...";
      voiceStatus.style.color = '#073824';
      processSpokenText(finalTranscript);
    } else {
      voiceStatus.textContent = "Tap to speak";
      voiceStatus.style.color = '#111827';
    }
  };

  async function processSpokenText(text) {
    try {
      const response = await fetch('/api/voice-process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ speech_text: text })
      });

      if (!response.ok) {
        throw new Error("Failed to process speech");
      }

      const data = await response.json();

      // Populate form fields
      if (descInput) descInput.value = data.transcript;
      if (titleInput) titleInput.value = data.title;
      if (locationInput && data.location) locationInput.value = data.location;
      if (categorySelect && data.category) categorySelect.value = data.category;
      if (prioritySelect && data.priority) prioritySelect.value = data.priority;
      if (isVoiceHidden) isVoiceHidden.value = "1";

      // Update "What we understood" sidecard
      const uType = document.getElementById('understoodType');
      const uLoc = document.getElementById('understoodLocation');
      const uPrio = document.getElementById('understoodPriority');
      if (uType && data.category) uType.textContent = data.category;
      if (uLoc && data.location) uLoc.textContent = data.location;
      if (uPrio && data.priority) uPrio.textContent = data.priority;

      // Show troubleshooting tips if available
      if (troubleshootingContainer && data.troubleshooting) {
        troubleshootingText.textContent = data.troubleshooting;
        troubleshootingContainer.style.display = 'block';
      }

      // Check missing fields and prompt user
      if (data.missing_fields && data.missing_fields.length > 0) {
        if (data.missing_fields.includes('location')) {
          voiceStatus.textContent = "⚠️ Spoken complaint captured! Please enter or confirm the exact Room or Building location below.";
          voiceStatus.style.color = '#fef08a';
          if (locationInput) {
            locationInput.focus();
            locationInput.style.borderColor = '#f59e0b';
          }
        }
      } else {
        voiceStatus.textContent = "✅ Voice input converted and classified! Please review details below before submitting.";
        voiceStatus.style.color = '#bbf7d0';
      }

      // Trigger duplicate check right away
      if (window.checkDuplicatesRealtime) {
        window.checkDuplicatesRealtime();
      }

    } catch (err) {
      console.error("AI engine processing error:", err);
      voiceStatus.textContent = "Audio captured. Please verify the populated details below.";
      if (descInput) descInput.value = text;
      if (titleInput && !titleInput.value) titleInput.value = text.substring(0, 50);
    }
  }
});
