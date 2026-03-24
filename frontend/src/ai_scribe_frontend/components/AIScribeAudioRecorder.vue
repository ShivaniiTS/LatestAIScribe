<template>
  <div class="audio-recorder-section">
    <!-- Recording Mode Selector -->
    <div class="mode-selector q-mb-lg">
      <q-btn-toggle
        v-model="recordingMode"
        spread
        no-caps
        rounded
        unelevated
        toggle-color="primary"
        color="white"
        text-color="primary"
        :options="[
          { label: 'Conversation + Notes', value: 'conversation' },
          { label: 'Dictation', value: 'dictation' }
        ]"
        :disable="isRecording || hasCurrentRecording || conversationRecording.completed || notesRecording.completed || dictationRecording.completed"
        class="mode-toggle"
      />
    </div>

    <!-- Current Recording Mode Header -->
    <div class="recording-mode-header q-mb-md">
      <div class="mode-icon-wrapper" :class="{ 'notes-mode': recordingType === 'notes', 'dictation-mode': recordingType === 'dictation' }">
        <q-icon 
          :name="recordingType === 'conversation' ? 'record_voice_over' : (recordingType === 'dictation' ? 'mic' : 'edit_note')" 
          size="28px" 
        />
      </div>
      <div class="mode-title" :class="{ 'notes-mode': recordingType === 'notes', 'dictation-mode': recordingType === 'dictation' }">
        {{ recordingMode === 'dictation' ? 'Dictation Recording' : (recordingType === 'conversation' ? 'Conversation Recording' : 'Notes Recording') }}
      </div>
      <div class="mode-description">
        {{ recordingMode === 'dictation' 
           ? 'Record your dictation for this encounter' 
           : (recordingType === 'conversation' 
              ? 'Record the patient-provider conversation' 
              : 'Add your notes for this encounter') }}
      </div>
    </div>

    <!-- Recording Interface -->
    <div class="recording-interface">
      <div class="waveform-container">
        <!-- Timer Badge -->
        <div class="timer-badge" :class="{ 'timer-active': isRecording }">
          {{ formatTime(recordingDuration) }}
        </div>
        
        <!-- Waveform Visualization Area -->
        <div class="waveform-wrapper">
          <canvas 
            ref="visualizerCanvas" 
            class="waveform-canvas"
          ></canvas>
          
          <!-- Flat line when not recording -->
          <div v-if="!isRecording && !hasCurrentRecording" class="waveform-placeholder">
            <div class="flat-line"></div>
          </div>
        </div>
      </div>

      <!-- Recording Controls -->
      <div class="recording-controls">
        <q-btn
          v-if="!isRecording && !hasCurrentRecording && !isCurrentTypeCompleted"
          rounded
          unelevated
          color="negative"
          text-color="white"
          icon="fiber_manual_record"
          :label="recordingType === 'conversation' ? 'Start Recording' : (recordingType === 'dictation' ? 'Record Dictation' : 'Record Notes')"
          class="control-btn record-btn"
          @click="startRecording(recordingType)"
        />
        <q-btn
          v-if="isRecording && !isPaused"
          rounded
          unelevated
          color="warning"
          text-color="white"
          icon="pause"
          label="Pause"
          class="control-btn"
          @click="pauseRecording"
        />
        <q-btn
          v-if="isRecording && isPaused"
          rounded
          unelevated
          color="positive"
          text-color="white"
          icon="play_arrow"
          label="Resume"
          class="control-btn"
          @click="resumeRecording"
        />
        <q-btn
          v-if="isRecording"
          rounded
          outline
          color="grey-6"
          icon="stop"
          label="Stop"
          class="control-btn stop-btn"
          @click="stopRecording"
        />
        
      </div>

      <!-- Audio Preview (after recording) -->
      <div v-if="hasCurrentRecording && !isRecording" class="audio-preview">
        <audio ref="audioPlayer" :src="currentAudioUrl" controls class="audio-player"></audio>
      </div>

      <!-- After recording completed - Save/Submit buttons -->
      <div v-if="hasCurrentRecording && !isRecording" class="recording-actions">
        <q-btn
          v-if="!isCurrentTypeCompleted"
          rounded
          unelevated
          color="primary"
          icon="save"
          :label="recordingMode === 'dictation' ? 'Submit Dictation' : (recordingType === 'conversation' ? 'Save Conversation' : 'Submit Recording')"
          :loading="isUploading"
          class="control-btn save-btn"
          @click="saveCurrentRecording"
        />
        <q-btn
          rounded
          flat
          color="grey-7"
          icon="delete_outline"
          label="Discard"
          class="control-btn"
          @click="discardCurrentRecording"
        />
      </div>

      <!-- Upload Progress -->
      <div v-if="isUploading" class="upload-progress">
        <q-linear-progress 
          :value="uploadProgress" 
          color="primary" 
          track-color="grey-3"
          rounded
          size="8px"
        />
        <div class="progress-text">Uploading... {{ Math.round(uploadProgress * 100) }}%</div>
      </div>
    </div>

    <!-- OR Divider -->
    <div class="or-divider">
      <span>- OR -</span>
    </div>

    <!-- Modern File Upload Area -->
    <div 
      class="upload-area"
      :class="{ 'drag-over': isDragging }"
      @dragover.prevent="isDragging = true"
      @dragleave.prevent="isDragging = false"
      @drop.prevent="handleDrop"
      @click="triggerFileUpload"
    >
      <input
        ref="fileInput"
        type="file"
        accept="audio/mp3,audio/wav,audio/m4a,audio/mpeg,.mp3,.wav,.m4a"
        style="display: none"
        @change="handleFileUpload"
      />
      
      <q-icon name="cloud_upload" size="48px" color="primary" class="upload-icon" />
      <div class="upload-title">
        {{ recordingType === 'conversation' ? 'Upload Conversation Audio' : (recordingType === 'dictation' ? 'Upload Dictation Audio' : 'Upload Notes Audio') }}
      </div>
      <div class="upload-subtitle">(or click to browse files)</div>
      <div class="upload-formats">
        Supported formats: .wav, .mp3, .m4a
      </div>
    </div>



    <!-- Success Message -->
    <q-slide-transition>
      <div v-if="uploadSuccess" class="success-message">
        <q-icon name="check_circle" color="positive" size="24px" />
        <span>Transcription is processing and generating the SOAP note. Go to AI Scribe history.</span>
      </div>
    </q-slide-transition>

    <!-- Notes Prompt Dialog -->
    <q-dialog v-model="showNotesPrompt" persistent>
      <q-card style="min-width: 400px; border-radius: 12px;">
        <q-card-section class="row items-center q-pb-none">
          <div class="text-h6">Add Dictation Notes?</div>
        </q-card-section>
        <q-card-section>
          <div class="text-body1">
            Would you like to add dictation notes to this conversation?
          </div>
        </q-card-section>
        <q-card-actions align="right" class="q-pa-md">
          <q-btn 
            flat 
            label="No, Submit Without Notes" 
            color="grey-7" 
            @click="skipNotes" 
          />
          <q-btn 
            unelevated 
            label="Yes, Add Notes" 
            color="primary" 
            @click="proceedToNotes" 
          />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </div>
</template>

<script setup>
import { ref, onUnmounted, watch, nextTick } from 'vue'
import { useQuasar } from 'quasar'
import { api } from 'boot/axios'

const $q = useQuasar()

// Props
const props = defineProps({
  formData: {
    type: Object,
    required: true
  }
})

// Emit events
const emit = defineEmits(['recording-submitted', 'recording-discarded'])

// Refs
const fileInput = ref(null)
const visualizerCanvas = ref(null)
const audioPlayer = ref(null)

// State
const isRecording = ref(false)
const isPaused = ref(false)
const recordingMode = ref('conversation') // 'conversation' or 'dictation'
const recordingType = ref('conversation')
const recordingDuration = ref(0)
const isUploading = ref(false)
const uploadProgress = ref(0)
const uploadSuccess = ref(false)
const isDragging = ref(false)
const notesSkipped = ref(false)
const showNotesPrompt = ref(false)
const isConverting = ref(false)

// Separate state for conversation and notes recordings
const conversationRecording = ref({
  completed: false,
  blob: null,
  url: null,
  duration: 0,
  fileName: ''
})

const notesRecording = ref({
  completed: false,
  blob: null,
  url: null,
  duration: 0,
  fileName: ''
})

// Separate state for dictation-only mode
const dictationRecording = ref({
  completed: false,
  blob: null,
  url: null,
  duration: 0,
  fileName: ''
})

// Current recording in progress (not yet saved)
const currentRecordingBlob = ref(null)
const currentRecordingUrl = ref(null)

// Computed properties
import { computed } from 'vue'

const canSubmit = computed(() => {
  // In dictation mode, only require dictation recording
  if (recordingMode.value === 'dictation') {
    return dictationRecording.value.completed
  }
  // In conversation mode, require conversation + optional notes
  return conversationRecording.value.completed && (notesRecording.value.completed || notesSkipped.value)
})

const hasCurrentRecording = computed(() => {
  return currentRecordingBlob.value !== null
})

const currentAudioUrl = computed(() => {
  return currentRecordingUrl.value
})

const isCurrentTypeCompleted = computed(() => {
  if (recordingType.value === 'conversation') {
    return conversationRecording.value.completed
  } else if (recordingType.value === 'dictation') {
    return dictationRecording.value.completed
  }
  return notesRecording.value.completed
})

// Audio recording objects
let mediaRecorder = null
let audioChunks = []
let audioContext = null
let analyser = null
let animationId = null
let timerInterval = null
let waveformHistory = []
const MAX_WAVEFORM_BARS = 60

// Format time as MM:SS
function formatTime(seconds) {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

// Start recording
async function startRecording(type) {
  recordingType.value = type
  uploadSuccess.value = false
  waveformHistory = []
  
  try {
    // Check if mediaDevices is available (requires HTTPS/secure context)
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error(
        'Microphone access requires a secure connection (HTTPS). ' +
        'Please ensure the app is served over HTTPS or use localhost.'
      )
    }
    
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        sampleRate: 48000,
        channelCount: 1
      }
    })

    // Set up audio context for visualization
    audioContext = new (window.AudioContext || window.webkitAudioContext)()
    analyser = audioContext.createAnalyser()
    analyser.fftSize = 256
    analyser.smoothingTimeConstant = 0.8
    const source = audioContext.createMediaStreamSource(stream)
    source.connect(analyser)

    await nextTick()
    visualize()

    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus'
      : MediaRecorder.isTypeSupported('audio/webm')
        ? 'audio/webm'
        : 'audio/mp4'

    mediaRecorder = new MediaRecorder(stream, {
      mimeType,
      audioBitsPerSecond: 128000
    })

    audioChunks = []

    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunks.push(event.data)
      }
    }

    mediaRecorder.onstop = async () => {
      const webmBlob = new Blob(audioChunks, { type: mimeType })
      
      stream.getTracks().forEach(track => track.stop())
      
      if (animationId) cancelAnimationFrame(animationId)
      if (audioContext) audioContext.close()
      
      // Convert to MP3
      isConverting.value = true
      try {
        const mp3Blob = await convertToMp3(webmBlob)
        currentRecordingBlob.value = mp3Blob
        currentRecordingUrl.value = URL.createObjectURL(mp3Blob)
      } catch (error) {
        console.error('Error converting to MP3:', error)
        // Fallback to original format if conversion fails
        currentRecordingBlob.value = webmBlob
        currentRecordingUrl.value = URL.createObjectURL(webmBlob)
        $q.notify({
          type: 'warning',
          message: 'Audio conversion failed, using original format',
          timeout: 3000
        })
      } finally {
        isConverting.value = false
      }
    }

    mediaRecorder.start(1000)
    isRecording.value = true
    isPaused.value = false
    recordingDuration.value = 0

    timerInterval = setInterval(() => {
      if (!isPaused.value) {
        recordingDuration.value++
      }
    }, 1000)

  } catch (error) {
    console.error('Error starting recording:', error)
    $q.notify({
      type: 'negative',
      message: 'Failed to access microphone',
      caption: error.message,
      timeout: 5000
    })
  }
}

// Waveform visualization with app's primary color
function visualize() {
  if (!analyser || !visualizerCanvas.value) return

  const canvas = visualizerCanvas.value
  const ctx = canvas.getContext('2d')
  
  const rect = canvas.getBoundingClientRect()
  canvas.width = rect.width * 2
  canvas.height = rect.height * 2
  ctx.scale(2, 2)

  const bufferLength = analyser.frequencyBinCount
  const dataArray = new Uint8Array(bufferLength)

  function draw() {
    animationId = requestAnimationFrame(draw)
    analyser.getByteFrequencyData(dataArray)

    const sum = dataArray.reduce((a, b) => a + b, 0)
    const avg = sum / bufferLength
    
    waveformHistory.push(avg)
    if (waveformHistory.length > MAX_WAVEFORM_BARS) {
      waveformHistory.shift()
    }

    ctx.clearRect(0, 0, rect.width, rect.height)

    const barWidth = rect.width / MAX_WAVEFORM_BARS
    const gap = 3
    const maxHeight = rect.height * 0.85
    const minHeight = 4
    const centerY = rect.height / 2

    waveformHistory.forEach((amplitude, i) => {
      const normalizedHeight = Math.max(minHeight, (amplitude / 255) * maxHeight)
      const x = i * barWidth + gap / 2
      const barW = barWidth - gap

      // Use blue color
      const gradient = ctx.createLinearGradient(0, centerY - normalizedHeight / 2, 0, centerY + normalizedHeight / 2)
      gradient.addColorStop(0, '#64B5F6')
      gradient.addColorStop(0.5, '#1976D2')
      gradient.addColorStop(1, '#64B5F6')

      ctx.fillStyle = gradient
      ctx.beginPath()
      ctx.roundRect(x, centerY - normalizedHeight / 2, barW, normalizedHeight, 3)
      ctx.fill()
    })
  }

  draw()
}

// Convert audio blob to MP3 format using lamejs
async function convertToMp3(audioBlob) {
  if (!audioBlob || audioBlob.size === 0) {
    throw new Error('Audio blob is empty')
  }

  // Create a temporary AudioContext for decoding
  const tempAudioContext = new (window.AudioContext || window.webkitAudioContext)()
  
  try {
    // Read the blob as an ArrayBuffer
    const arrayBuffer = await audioBlob.arrayBuffer()
    
    // Decode the audio data
    const audioBuffer = await tempAudioContext.decodeAudioData(arrayBuffer)
    
    // Get audio data (convert to mono if stereo)
    const numberOfChannels = audioBuffer.numberOfChannels
    const sampleRate = audioBuffer.sampleRate
    let samples
    
    if (numberOfChannels === 2) {
      // Mix stereo to mono
      const left = audioBuffer.getChannelData(0)
      const right = audioBuffer.getChannelData(1)
      samples = new Float32Array(left.length)
      for (let i = 0; i < left.length; i++) {
        samples[i] = (left[i] + right[i]) / 2
      }
    } else {
      samples = audioBuffer.getChannelData(0)
    }
    
    // Convert Float32Array to Int16Array for lamejs
    const sampleCount = samples.length
    const int16Samples = new Int16Array(sampleCount)
    for (let i = 0; i < sampleCount; i++) {
      const s = Math.max(-1, Math.min(1, samples[i]))
      int16Samples[i] = s < 0 ? s * 0x8000 : s * 0x7FFF
    }
    
    // Encode to MP3 using lamejs
    // eslint-disable-next-line no-undef
    const mp3Encoder = new lamejs.Mp3Encoder(1, sampleRate, 128) // mono, sample rate, 128kbps
    const mp3Data = []
    
    // Process in chunks of 1152 samples (required by lamejs)
    const chunkSize = 1152
    for (let i = 0; i < int16Samples.length; i += chunkSize) {
      const chunk = int16Samples.subarray(i, Math.min(i + chunkSize, int16Samples.length))
      const mp3buf = mp3Encoder.encodeBuffer(chunk)
      if (mp3buf.length > 0) {
        mp3Data.push(mp3buf)
      }
    }
    
    // Flush the encoder
    const finalBuf = mp3Encoder.flush()
    if (finalBuf.length > 0) {
      mp3Data.push(finalBuf)
    }
    
    // Create MP3 blob
    const mp3Blob = new Blob(mp3Data, { type: 'audio/mp3' })
    return mp3Blob
    
  } finally {
    await tempAudioContext.close()
  }
}

function pauseRecording() {
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.pause()
    isPaused.value = true
  }
}

function resumeRecording() {
  if (mediaRecorder && mediaRecorder.state === 'paused') {
    mediaRecorder.resume()
    isPaused.value = false
  }
}

function stopRecording() {
  if (mediaRecorder && (mediaRecorder.state === 'recording' || mediaRecorder.state === 'paused')) {
    mediaRecorder.stop()
    isRecording.value = false
    isPaused.value = false
    if (timerInterval) clearInterval(timerInterval)
  }
}

function triggerFileUpload() {
  fileInput.value?.click()
}

function handleDrop(event) {
  isDragging.value = false
  const file = event.dataTransfer.files[0]
  if (file) {
    if (validateFileType(file)) {
      processUploadedFile(file)
    }
  }
}

function handleFileUpload(event) {
  const file = event.target.files[0]
  if (!file) return
  
  if (validateFileType(file)) {
    processUploadedFile(file)
  }
  event.target.value = ''
}

function validateFileType(file) {
  const validTypes = ['audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/x-wav', 'audio/m4a', 'audio/x-m4a', 'audio/mp4']
  const validExtensions = ['.mp3', '.wav', '.m4a']
  
  const fileType = file.type.toLowerCase()
  const fileName = file.name.toLowerCase()
  
  const isValidType = validTypes.some(type => fileType.includes(type))
  const isValidExtension = validExtensions.some(ext => fileName.endsWith(ext))
  
  if (!isValidType && !isValidExtension) {
    $q.notify({
      type: 'negative',
      message: 'Unsupported file format',
      caption: 'Please upload .mp3, .wav, or .m4a files only',
      timeout: 5000
    })
    return false
  }
  return true
}

function processUploadedFile(file) {
  // Auto-determine type based on workflow state and mode
  if (canSubmit.value) {
    $q.notify({ type: 'warning', message: 'Recording is already complete. Please submit or start over.', timeout: 5000 })
    return
  }
  
  // In dictation mode, always set type to dictation
  let type
  let displayType
  if (recordingMode.value === 'dictation') {
    type = 'dictation'
    displayType = 'Dictation'
  } else {
    type = conversationRecording.value.completed ? 'notes' : 'conversation'
    displayType = type === 'conversation' ? 'Conversation' : 'Notes'
  }
  
  recordingType.value = type
  currentRecordingBlob.value = file
  currentRecordingUrl.value = URL.createObjectURL(file)
  uploadSuccess.value = false
  recordingDuration.value = 0
  
  $q.notify({
    type: 'info',
    message: `File loaded as ${displayType} recording`,
    caption: 'Review and save when ready',
    timeout: 3000
  })
}

// Save current recording to the appropriate type
async function saveCurrentRecording() {
  if (!currentRecordingBlob.value) return
  
  // In dictation mode, save as dictation and submit immediately
  if (recordingMode.value === 'dictation') {
    dictationRecording.value = {
      completed: true,
      blob: currentRecordingBlob.value,
      url: currentRecordingUrl.value,
      duration: recordingDuration.value,
      fileName: ''
    }
    
    // Clear current recording before submitting
    currentRecordingBlob.value = null
    currentRecordingUrl.value = null
    recordingDuration.value = 0
    
    // Immediately submit dictation
    await submitAllRecordings()
    return
  }
  
  if (recordingType.value === 'conversation') {
    conversationRecording.value = {
      completed: true,
      blob: currentRecordingBlob.value,
      url: currentRecordingUrl.value,
      duration: recordingDuration.value,
      fileName: ''
    }
    
    // Clear current recording
    currentRecordingBlob.value = null
    currentRecordingUrl.value = null
    recordingDuration.value = 0
    
    // Show notes prompt dialog
    showNotesPrompt.value = true
    return
  } else {
    // Save notes and immediately submit
    notesRecording.value = {
      completed: true,
      blob: currentRecordingBlob.value,
      url: currentRecordingUrl.value,
      duration: recordingDuration.value,
      fileName: ''
    }
    
    // Clear current recording before submitting
    currentRecordingBlob.value = null
    currentRecordingUrl.value = null
    recordingDuration.value = 0
    
    // Immediately submit both recordings
    await submitAllRecordings()
    return
  }
}

// User chose to add notes
function proceedToNotes() {
  showNotesPrompt.value = false
  recordingType.value = 'notes'
  $q.notify({
    type: 'positive',
    message: 'Conversation saved',
    caption: 'Now please record your notes',
    timeout: 3000
  })
}

// User chose to skip notes
async function skipNotes() {
  showNotesPrompt.value = false
  notesSkipped.value = true
  
  $q.notify({
    type: 'info',
    message: 'Notes skipped',
    caption: 'Submitting conversation only',
    timeout: 3000
  })
  
  // Immediately submit with just conversation
  await submitAllRecordings()
}

// Discard current recording (not saved yet)
function discardCurrentRecording() {
  if (currentRecordingUrl.value) URL.revokeObjectURL(currentRecordingUrl.value)
  currentRecordingBlob.value = null
  currentRecordingUrl.value = null
  recordingDuration.value = 0
  waveformHistory = []
}

// Reset all recordings and start over
function resetAllRecordings() {
  if (conversationRecording.value.url) URL.revokeObjectURL(conversationRecording.value.url)
  if (notesRecording.value.url) URL.revokeObjectURL(notesRecording.value.url)
  if (dictationRecording.value.url) URL.revokeObjectURL(dictationRecording.value.url)
  if (currentRecordingUrl.value) URL.revokeObjectURL(currentRecordingUrl.value)
  
  conversationRecording.value = { completed: false, blob: null, url: null, duration: 0, fileName: '' }
  notesRecording.value = { completed: false, blob: null, url: null, duration: 0, fileName: '' }
  dictationRecording.value = { completed: false, blob: null, url: null, duration: 0, fileName: '' }
  currentRecordingBlob.value = null
  currentRecordingUrl.value = null
  // Reset recordingType based on current mode
  recordingType.value = recordingMode.value === 'dictation' ? 'dictation' : 'conversation'
  recordingDuration.value = 0
  uploadSuccess.value = false
  notesSkipped.value = false
  showNotesPrompt.value = false
  waveformHistory = []
  
  emit('recording-discarded')
}

async function submitAllRecordings() {
  if (!canSubmit.value) {
    const msg = recordingMode.value === 'dictation' 
      ? 'Please complete the dictation recording first' 
      : 'Please complete the conversation recording first'
    $q.notify({ type: 'warning', message: msg, timeout: 5000 })
    return
  }

  const guarantorId = props.formData.guarantor_id
  const appointmentId = props.formData.appointment_id
  const caseId = props.formData.case_number
  const encounterId = props.formData.encounter_id || props.formData.appointment_id

  if (!guarantorId || !appointmentId || !caseId) {
    $q.notify({
      type: 'negative',
      message: 'Missing required patient information',
      caption: 'Guarantor ID, Appointment ID, and Case ID are required',
      timeout: 5000
    })
    return
  }

  isUploading.value = true
  uploadProgress.value = 0

  try {
    // In dictation mode, upload dictation recording
    if (recordingMode.value === 'dictation' && dictationRecording.value.blob) {
      await uploadSingleRecording(dictationRecording.value.blob, 'dictation', encounterId, guarantorId, appointmentId, caseId)
    } else {
      // In conversation mode, upload conversation
      if (conversationRecording.value.blob) {
        await uploadSingleRecording(conversationRecording.value.blob, 'conversation', encounterId, guarantorId, appointmentId, caseId)
      }
      
      // Upload notes recording only if completed
      if (notesRecording.value.completed && notesRecording.value.blob) {
        await uploadSingleRecording(notesRecording.value.blob, 'notes', encounterId, guarantorId, appointmentId, caseId)
      }
    }
    
    // Upload demographics once
    await uploadDemographics()
    
    uploadSuccess.value = true
    
    // Show appropriate success message
    const isDictation = recordingMode.value === 'dictation'
    const hasNotes = notesRecording.value.completed && notesRecording.value.blob
    const hasConversation = conversationRecording.value.completed && conversationRecording.value.blob
    
    let message, caption, emitType
    if (isDictation) {
      message = 'Dictation uploaded successfully'
      caption = 'Dictation has been saved'
      emitType = 'dictation'
    } else if (hasNotes && hasConversation) {
      message = 'Both recordings uploaded successfully'
      caption = 'Conversation and Notes have been saved'
      emitType = 'both'
    } else {
      message = 'Conversation uploaded successfully'
      caption = 'Conversation has been saved'
      emitType = 'conversation'
    }
    
    $q.notify({ type: 'positive', message, caption, timeout: 5000 })
    
    emit('recording-submitted', { type: emitType })

    setTimeout(() => {
      resetAllRecordings()
      uploadSuccess.value = true
    }, 2000)


  } catch (error) {
    console.error('Error uploading recordings:', error)
    $q.notify({
      type: 'negative',
      message: 'Failed to upload recordings',
      caption: error.message,
      timeout: 5000
    })
  } finally {
    isUploading.value = false
    uploadProgress.value = 0
  }
}

async function uploadSingleRecording(blob, audioType, encounterId, guarantorId, appointmentId, caseId) {
  const formData = new FormData()
  
  const mimeType = blob.type
  let extension = 'mp3'
  if (mimeType.includes('webm')) extension = 'webm'
  else if (mimeType.includes('wav')) extension = 'wav'
  else if (mimeType.includes('m4a') || mimeType.includes('mp4')) extension = 'm4a'
  
  const fileName = `${encounterId}_${audioType}.${extension}`
  formData.append('file', blob, fileName)
  formData.append('guarantor_id', String(guarantorId))
  formData.append('appointment_id', String(appointmentId))
  formData.append('case_id', String(caseId))
  formData.append('encounter_id', String(encounterId))
  formData.append('audio_type', audioType)
  
  // Include demographics with first (conversation) upload so encounter is created with patient info
  if (audioType === 'conversation') {
    const demographics = {
      date: props.formData.date || '',
      patient_name: props.formData.patient_name || '',
      account_number: props.formData.account_number || '',
      case_name: props.formData.case_name || '',
      case_number: props.formData.case_number || '',
      location_code: props.formData.location_code || '',
      location_name: props.formData.location_name || '',
      provider_name: props.formData.provider_name || '',
      rendering_provider: props.formData.rendering_provider_id || '',
      d_o_b: props.formData.d_o_b || '',
      injury_date: props.formData.injury_date || ''
    }
    formData.append('demographics', JSON.stringify(demographics))
  }

  const response = await api.post('/api/upload-audio', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000, // 120 seconds for large audio files
    onUploadProgress: (progressEvent) => {
      // Show progress for each upload (0-50% for conversation, 50-100% for notes)
      const base = audioType === 'conversation' ? 0 : 0.5
      uploadProgress.value = base + (progressEvent.loaded / progressEvent.total) * 0.5
    }
  })

  if (!response.data.success) {
    throw new Error(response.data.error || `Failed to upload ${audioType}`)
  }
  
  return response.data
}

async function uploadDemographics() {
  const guarantorId = props.formData.guarantor_id
  const appointmentId = props.formData.appointment_id
  const caseId = props.formData.case_number
  const encounterId = props.formData.encounter_id || props.formData.appointment_id

  if (!guarantorId || !appointmentId || !caseId) return

  try {
    const demographics = {
      date: props.formData.date || '',
      patient_name: props.formData.patient_name || '',
      account_number: props.formData.account_number || '',
      case_name: props.formData.case_name || '',
      case_number: props.formData.case_number || '',
      location_code: props.formData.location_code || '',
      location_name: props.formData.location_name || '',
      provider_name: props.formData.provider_name || '',
      provider_id: props.formData.provider_id || null,
      rendering_provider: props.formData.rendering_provider_id || '',
      guarantor_id: props.formData.guarantor_id || '',
      d_o_b: props.formData.d_o_b || '',
      num_pt_visits: props.formData.num_pt_visits || 0,
      injury_date: props.formData.injury_date || '',
      case_desc: props.formData.case_desc || '',
      cost_center_desc: props.formData.cost_center_desc || '',
      primary_carrier: props.formData.primary_carrier || '',
      appointment_id: props.formData.appointment_id || null,
      encounter_id: props.formData.encounter_id || null
    }

    await api.post('/api/upload-demographics-v2', {
      guarantor_id: String(guarantorId),
      appointment_id: String(appointmentId),
      case_id: String(caseId),
      encounter_id: String(encounterId),
      demographics
    })
  } catch (error) {
    console.error('Error uploading demographics:', error)
  }
}

onUnmounted(() => {
  if (timerInterval) clearInterval(timerInterval)
  if (animationId) cancelAnimationFrame(animationId)
  if (audioContext) audioContext.close()
  if (currentRecordingUrl.value) URL.revokeObjectURL(currentRecordingUrl.value)
  if (conversationRecording.value.url) URL.revokeObjectURL(conversationRecording.value.url)
  if (notesRecording.value.url) URL.revokeObjectURL(notesRecording.value.url)
})

watch(audioPlayer, (player) => {
  if (player) {
    player.onloadedmetadata = () => {
      if (player.duration && !isNaN(player.duration) && recordingDuration.value === 0) {
        recordingDuration.value = Math.round(player.duration)
      }
    }
  }
})

// Watch for recording mode changes to update recordingType
watch(recordingMode, (newMode) => {
  // Only update if no recording in progress
  if (!isRecording.value && !hasCurrentRecording.value && !conversationRecording.value.completed && !notesRecording.value.completed && !dictationRecording.value.completed) {
    recordingType.value = newMode === 'dictation' ? 'dictation' : 'conversation'
  }
})
</script>

<style scoped>
.audio-recorder-section {
  background: #ffffff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 16px;
}

.type-tabs {
  display: flex;
  justify-content: center;
}

.mode-selector {
  display: flex;
  justify-content: center;
}

.mode-toggle {
  border: 2px solid #1976d2;
  border-radius: 28px;
  max-width: 400px;
  width: 100%;
}

.mode-toggle .q-btn {
  font-weight: 600;
}

.type-toggle {
  border: 1px solid #e0e0e0;
  border-radius: 24px;
}

/* Recording Interface */
.recording-interface {
  background: linear-gradient(135deg, #e3f2fd 0%, #f5f9ff 50%, #fafcff 100%);
  border-radius: 16px;
  padding: 24px;
  border: 1px solid #bbdefb;
}

.waveform-container {
  position: relative;
  background: white;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  min-height: 140px;
}

.timer-badge {
  position: absolute;
  top: 12px;
  right: 12px;
  background: #fff;
  color: #333;
  padding: 8px 16px;
  border-radius: 8px;
  font-family: 'Courier New', monospace;
  font-weight: 700;
  font-size: 16px;
  border: 1px solid #e0e0e0;
  transition: all 0.3s ease;
}

.timer-active {
  background: #e3f2fd;
  color: #1565c0;
  border-color: #90caf9;
}

.waveform-wrapper {
  width: 100%;
  height: 100px;
  position: relative;
}

.waveform-canvas {
  width: 100%;
  height: 100%;
}

.waveform-placeholder {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.flat-line {
  width: 100%;
  height: 2px;
  background: linear-gradient(90deg, transparent 0%, #1976D2 20%, #1976D2 80%, transparent 100%);
  opacity: 0.4;
}

.recording-controls {
  display: flex;
  justify-content: center;
  gap: 16px;
  flex-wrap: wrap;
}

.control-btn {
  padding: 12px 32px;
  font-weight: 600;
  font-size: 14px;
}

.record-btn {
  min-width: 140px;
}

.stop-btn {
  background: white !important;
}

.audio-preview {
  margin-top: 16px;
  margin-bottom: 16px;
}

.audio-player {
  width: 100%;
  height: 42px;
  border-radius: 8px;
}

.recording-actions {
  display: flex;
  justify-content: center;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.upload-progress {
  margin-top: 16px;
}

.progress-text {
  text-align: center;
  font-size: 12px;
  color: #1976d2;
  margin-top: 8px;
  font-weight: 500;
}

/* OR Divider */
.or-divider {
  text-align: center;
  margin: 24px 0;
  color: #999;
  font-size: 13px;
  font-weight: 500;
}

/* Upload Area */
.upload-area {
  background: linear-gradient(135deg, #e3f2fd 0%, #f5f9ff 100%);
  border: 2px dashed #1976D2;
  border-radius: 12px;
  padding: 40px 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s ease;
}

.upload-area:hover {
  background: #e3f2fd;
  border-color: #1565c0;
}

.upload-area.drag-over {
  background: #e3f2fd;
  border-color: #1565c0;
  transform: scale(1.01);
}

.upload-icon {
  margin-bottom: 12px;
}

.upload-title {
  font-size: 18px;
  font-weight: 600;
  color: #333;
  margin-bottom: 4px;
}

.upload-subtitle {
  font-size: 14px;
  color: #666;
  margin-bottom: 12px;
}

.upload-formats {
  font-size: 11px;
  color: #999;
  max-width: 400px;
  margin: 0 auto;
}

/* Upload Dialog */
.upload-dialog {
  min-width: 380px;
  border-radius: 12px;
}

.upload-type-options {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.upload-type-btn {
  padding: 16px 24px;
  font-weight: 500;
  justify-content: flex-start;
}

/* Success Message */
.success-message {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: #e8f5e9;
  color: #2e7d32;
  padding: 12px 20px;
  border-radius: 8px;
  margin-top: 16px;
  font-weight: 500;
}

/* Recording Mode Header */
.recording-mode-header {
  text-align: center;
  padding: 20px 16px;
  background: linear-gradient(135deg, #f8fafc 0%, #e3f2fd 100%);
  border-radius: 12px;
  border: 1px solid #e0e0e0;
}

.mode-icon-wrapper {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  background: #e3f2fd;
  border-radius: 50%;
  margin-bottom: 8px;
  color: #1976D2;
}

.mode-icon-wrapper.notes-mode {
  background: #f3e5f5;
  color: #7B1FA2;
}

.mode-title {
  font-size: 20px;
  font-weight: 600;
  color: #1976D2;
  margin-bottom: 4px;
}

.mode-title.notes-mode {
  color: #7B1FA2;
}

.mode-description {
  color: #666;
  font-size: 14px;
}

.save-btn {
  min-width: 180px;
}

/* Submit Section */
.submit-section {
  background: #ffffff;
  border: 1px solid #e0e0e0;
  border-radius: 12px;
  padding: 24px;
  text-align: center;
}

.submit-ready-message {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #2e7d32;
  font-weight: 600;
  font-size: 15px;
}

.submit-btn {
  padding: 14px 40px;
  font-size: 16px;
  font-weight: 600;
}

/* Completed Badge */
.completed-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  background: #e8f5e9;
  border: 1px solid #a5d6a7;
  border-radius: 20px;
  color: #2e7d32;
  font-weight: 500;
  font-size: 14px;
}
</style>
