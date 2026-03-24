<template>
  <q-layout view="lHh Lpr lFf">
    <q-header elevated>
      <q-toolbar>
        <q-btn flat dense round icon="menu" aria-label="Menu" @click="toggleLeftDrawer" />
        <q-toolbar-title>Excelsia Web Portal</q-toolbar-title>
      </q-toolbar>
    </q-header>

    <q-drawer v-model="leftDrawerOpen" bordered>
      <q-list>
        <q-item to="/" exact clickable v-ripple>
          <q-item-section>
            <q-item-label>
              <q-icon name="home" class="q-mr-sm" />
              Dashboard
            </q-item-label>
          </q-item-section>
        </q-item>
        <q-item to="/md-checkout-main" exact clickable v-ripple>
          <q-item-section>
            <q-item-label>
              <q-icon name="assignment" class="q-mr-sm" />
              MDCO Form
            </q-item-label>
          </q-item-section>
        </q-item>
        <q-item to="/forms/ai-scribe" clickable v-ripple>
          <q-item-section>
            <q-item-label>
              <q-icon name="mic" class="q-mr-sm" />
              AI Scribe
            </q-item-label>
          </q-item-section>
        </q-item>
        <q-item to="/soap-history" exact clickable v-ripple>
          <q-item-section>
            <q-item-label>
              <q-icon name="schedule" class="q-mr-sm" />
              AI Scribe History
            </q-item-label>
          </q-item-section>
        </q-item>
        <q-item to="/help" exact clickable v-ripple>
          <q-item-section>
            <q-item-label>
              <q-icon name="help" class="q-mr-sm" />
              Help
            </q-item-label>
          </q-item-section>
        </q-item>
      </q-list>
    </q-drawer>

    <q-page-container>
      <router-view />
    </q-page-container>
  </q-layout>
</template>

<script setup>
import { ref } from 'vue'

const leftDrawerOpen = ref(false)

function toggleLeftDrawer() {
  leftDrawerOpen.value = !leftDrawerOpen.value
}
</script>
