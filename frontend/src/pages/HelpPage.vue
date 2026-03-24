<template>
  <q-page class="q-pa-xl">
    <div class="text-h5 q-mb-md"><q-icon name="help" class="q-mr-sm" />Help & Documentation</div>
    <q-list bordered separator>
      <q-expansion-item icon="mic" label="How to use AI Scribe" default-opened>
        <q-card>
          <q-card-section>
            <ol>
              <li>Go to <b>MDCO Form</b> and select a provider and appointment date.</li>
              <li>Click <b>AI Scribe</b> next to a patient to open the recording page.</li>
              <li>Choose <b>Conversation + Notes</b> or <b>Dictation</b> mode.</li>
              <li>Click <b>Start Recording</b> and speak. Click <b>Stop</b> when done.</li>
              <li>Review the audio preview, then click <b>Save / Submit</b>.</li>
              <li>Go to <b>AI Scribe History</b> to view the generated SOAP note once processing completes.</li>
            </ol>
          </q-card-section>
        </q-card>
      </q-expansion-item>
      <q-expansion-item icon="upload" label="Uploading an existing audio file">
        <q-card>
          <q-card-section>
            On the AI Scribe page, drag and drop an audio file (.mp3, .wav, .m4a) onto the upload area, or click to browse.
            Supported formats: MP3, WAV, M4A.
          </q-card-section>
        </q-card>
      </q-expansion-item>
      <q-expansion-item icon="history" label="Viewing AI Scribe History">
        <q-card>
          <q-card-section>
            Click <b>AI Scribe History</b> in the sidebar. The table shows all submitted recordings with their status.
            Once processing is complete, click the SOAP icon to view the generated clinical note.
          </q-card-section>
        </q-card>
      </q-expansion-item>
      <q-expansion-item icon="contact_support" label="Contact / Support">
        <q-card>
          <q-card-section>
            For technical support, contact your system administrator.
          </q-card-section>
        </q-card>
      </q-expansion-item>
    </q-list>
  </q-page>
</template>

<script setup>
</script>
