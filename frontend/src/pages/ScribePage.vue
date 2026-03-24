<template>
  <q-page class="page-container">
    <div class="text-h4 q-mb-md">New Encounter</div>

    <!-- Step 1: Encounter setup -->
    <q-card class="q-mb-md" v-if="!encounterId">
      <q-card-section>
        <div class="text-h6 q-mb-sm">Setup</div>
        <div class="row q-col-gutter-md">
          <div class="col-12 col-sm-6">
            <q-input v-model="form.provider_id" label="Provider ID" outlined />
          </div>
          <div class="col-12 col-sm-6">
            <q-input v-model="form.patient_id" label="Patient ID (optional)" outlined />
          </div>
          <div class="col-12 col-sm-6">
            <q-select v-model="form.visit_type" :options="visitTypes" label="Visit Type" outlined />
          </div>
          <div class="col-12 col-sm-6">
            <q-select v-model="form.mode" :options="modes" label="Recording Mode" outlined />
          </div>
        </div>
      </q-card-section>
      <q-card-actions align="right">
        <q-btn color="primary" label="Create Encounter" @click="createEncounter" :loading="creating" />
      </q-card-actions>
    </q-card>

    <!-- Step 2: Recording -->
    <q-card class="q-mb-md" v-if="encounterId && !uploaded">
      <q-card-section>
        <div class="text-h6 q-mb-sm">Record Audio — {{ encounterId }}</div>

        <!-- Waveform visualization -->
        <canvas ref="canvasRef" class="waveform-canvas q-mb-md" />

        <div class="row q-gutter-md items-center justify-center q-mb-md">
          <q-btn v-if="!recording" round color="negative" icon="mic" size="lg"
            :class="{ 'recording-active': recording }" @click="startRecording" />
          <q-btn v-if="recording && !paused" round color="grey" icon="pause" size="lg"
            @click="pauseRecording" />
          <q-btn v-if="recording && paused" round color="positive" icon="play_arrow" size="lg"
            @click="resumeRecording" />
          <q-btn v-if="recording" round color="dark" icon="stop" size="lg"
            @click="stopRecording" />
        </div>

        <div class="text-center text-h5 q-mb-md">{{ formatTime(elapsed) }}</div>

        <!-- Or upload file -->
        <q-separator class="q-my-md" />
        <q-file v-model="audioFile" label="Or upload an audio file" outlined accept="audio/*"
          @update:model-value="onFileSelected">
          <template v-slot:prepend><q-icon name="attach_file" /></template>
        </q-file>
      </q-card-section>
      <q-card-actions align="right">
        <q-btn color="primary" label="Upload & Process" @click="uploadAudio"
          :loading="uploading" :disable="!audioBlob && !audioFile" />
      </q-card-actions>
    </q-card>

    <!-- Step 3: Pipeline progress -->
    <q-card v-if="uploaded">
      <q-card-section>
        <div class="text-h6">Pipeline Progress — {{ encounterId }}</div>
        <q-linear-progress :value="progress / 100" size="24px" color="primary" class="q-mt-md q-mb-sm">
          <div class="absolute-full flex flex-center">
            <q-badge color="white" text-color="primary" :label="`${progress}%`" />
          </div>
        </q-linear-progress>
        <div class="text-body2 text-grey-7">{{ stageMessage }}</div>

        <q-banner v-if="pipelineError" class="bg-negative text-white q-mt-md">
          {{ pipelineError }}
        </q-banner>

        <div v-if="pipelineComplete" class="q-mt-md">
          <q-btn color="primary" label="View Results" :to="'/encounters/' + encounterId" />
        </div>
      </q-card-section>
    </q-card>
  </q-page>
</template>

<script setup>
import { ref, onUnmounted } from 'vue'
import { api } from 'boot/axios'
import { useQuasar } from 'quasar'

const $q = useQuasar()

const form = ref({
  provider_id: '',
  patient_id: '',
  visit_type: 'follow_up',
  mode: 'dictation',
})
const visitTypes = ['follow_up', 'new_patient', 'annual_physical', 'consultation']
const modes = ['dictation', 'ambient']

const encounterId = ref(null)
const creating = ref(false)
const uploading = ref(false)
const uploaded = ref(false)

// Recording
const recording = ref(false)
const paused = ref(false)
const elapsed = ref(0)
const audioBlob = ref(null)
const audioFile = ref(null)
const canvasRef = ref(null)

let mediaRecorder = null
let audioChunks = []
let timerInterval = null
let audioContext = null
let analyser = null
let animationFrame = null
let ws = null

function formatTime (secs) {
  const m = Math.floor(secs / 60).toString().padStart(2, '0')
  const s = (secs % 60).toString().padStart(2, '0')
  return `${m}:${s}`
}

async function createEncounter () {
  if (!form.value.provider_id) {
    $q.notify({ type: 'warning', message: 'Provider ID is required' })
    return
  }
  creating.value = true
  try {
    const { data } = await api.post('/encounters', form.value)
    encounterId.value = data.encounter_id
    $q.notify({ type: 'positive', message: `Encounter ${data.encounter_id} created` })
  } catch (e) {
    $q.notify({ type: 'negative', message: e.response?.data?.detail || 'Failed to create encounter' })
  } finally {
    creating.value = false
  }
}

async function startRecording () {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })
    audioChunks = []

    mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) audioChunks.push(e.data) }
    mediaRecorder.onstop = () => {
      audioBlob.value = new Blob(audioChunks, { type: 'audio/webm' })
      stream.getTracks().forEach(t => t.stop())
      cancelAnimationFrame(animationFrame)
    }

    mediaRecorder.start(250)
    recording.value = true
    paused.value = false
    elapsed.value = 0
    timerInterval = setInterval(() => { elapsed.value++ }, 1000)

    // Waveform
    audioContext = new AudioContext()
    const source = audioContext.createMediaStreamSource(stream)
    analyser = audioContext.createAnalyser()
    analyser.fftSize = 256
    source.connect(analyser)
    drawWaveform()
  } catch (e) {
    $q.notify({ type: 'negative', message: 'Microphone access denied' })
  }
}

function drawWaveform () {
  if (!canvasRef.value || !analyser) return
  const canvas = canvasRef.value
  const ctx = canvas.getContext('2d')
  const bufferLength = analyser.frequencyBinCount
  const dataArray = new Uint8Array(bufferLength)

  function draw () {
    animationFrame = requestAnimationFrame(draw)
    analyser.getByteTimeDomainData(dataArray)
    ctx.fillStyle = '#f5f5f5'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.lineWidth = 2
    ctx.strokeStyle = recording.value ? '#c10015' : '#1976d2'
    ctx.beginPath()
    const sliceWidth = canvas.width / bufferLength
    let x = 0
    for (let i = 0; i < bufferLength; i++) {
      const v = dataArray[i] / 128.0
      const y = (v * canvas.height) / 2
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
      x += sliceWidth
    }
    ctx.lineTo(canvas.width, canvas.height / 2)
    ctx.stroke()
  }
  draw()
}

function pauseRecording () {
  if (mediaRecorder?.state === 'recording') {
    mediaRecorder.pause()
    paused.value = true
    clearInterval(timerInterval)
  }
}

function resumeRecording () {
  if (mediaRecorder?.state === 'paused') {
    mediaRecorder.resume()
    paused.value = false
    timerInterval = setInterval(() => { elapsed.value++ }, 1000)
  }
}

function stopRecording () {
  if (mediaRecorder) {
    mediaRecorder.stop()
    recording.value = false
    paused.value = false
    clearInterval(timerInterval)
    if (audioContext) audioContext.close()
  }
}

function onFileSelected () {
  audioBlob.value = null // Prefer file upload
}

// Pipeline progress
const progress = ref(0)
const stageMessage = ref('')
const pipelineError = ref(null)
const pipelineComplete = ref(false)

async function uploadAudio () {
  uploading.value = true
  try {
    const formData = new FormData()
    if (audioFile.value) {
      formData.append('audio', audioFile.value)
    } else if (audioBlob.value) {
      formData.append('audio', audioBlob.value, 'recording.webm')
    } else {
      return
    }

    await api.post(`/encounters/${encounterId.value}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
    })

    uploaded.value = true
    connectWebSocket()
  } catch (e) {
    $q.notify({ type: 'negative', message: e.response?.data?.detail || 'Upload failed' })
  } finally {
    uploading.value = false
  }
}

function connectWebSocket () {
  const base = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace('http', 'ws')
  ws = new WebSocket(`${base}/ws/encounters/${encounterId.value}`)

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    if (data.type === 'progress') {
      progress.value = data.pct || 0
      stageMessage.value = data.message || data.stage || ''
    } else if (data.type === 'complete') {
      progress.value = 100
      stageMessage.value = 'Complete!'
      pipelineComplete.value = true
      $q.notify({ type: 'positive', message: 'Pipeline complete' })
    } else if (data.type === 'error') {
      pipelineError.value = data.error
      $q.notify({ type: 'negative', message: data.error })
    }
  }

  ws.onerror = () => { pipelineError.value = 'WebSocket connection error' }

  // Send keepalive pings
  const pingInterval = setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) ws.send('ping')
    else clearInterval(pingInterval)
  }, 25000)
}

onUnmounted(() => {
  clearInterval(timerInterval)
  cancelAnimationFrame(animationFrame)
  if (ws) ws.close()
  if (audioContext) audioContext.close()
})
</script>
