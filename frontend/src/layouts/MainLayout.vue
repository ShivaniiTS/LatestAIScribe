<template>
  <q-layout view="lHh Lpr lFf">
    <q-header elevated class="bg-primary text-white">
      <q-toolbar>
        <q-btn flat dense round icon="menu" aria-label="Menu" @click="toggleLeftDrawer" />
        <q-toolbar-title>AI Scribe Enterprise</q-toolbar-title>
        <q-btn flat round dense icon="notifications" />
      </q-toolbar>
    </q-header>

    <q-drawer v-model="leftDrawerOpen" show-if-above bordered>
      <q-list>
        <q-item-label header class="text-grey-8">Navigation</q-item-label>

        <q-item clickable v-ripple to="/" exact>
          <q-item-section avatar><q-icon name="dashboard" /></q-item-section>
          <q-item-section>Dashboard</q-item-section>
        </q-item>

        <q-item clickable v-ripple to="/scribe">
          <q-item-section avatar><q-icon name="mic" /></q-item-section>
          <q-item-section>New Encounter</q-item-section>
        </q-item>

        <q-item clickable v-ripple to="/history">
          <q-item-section avatar><q-icon name="history" /></q-item-section>
          <q-item-section>History</q-item-section>
        </q-item>

        <q-separator spaced />
        <q-item-label header class="text-grey-8">Admin</q-item-label>

        <q-item clickable v-ripple to="/mt-review">
          <q-item-section avatar><q-icon name="rate_review" /></q-item-section>
          <q-item-section>MT Review</q-item-section>
        </q-item>

        <q-item clickable v-ripple to="/providers">
          <q-item-section avatar><q-icon name="people" /></q-item-section>
          <q-item-section>Providers</q-item-section>
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
function toggleLeftDrawer () {
  leftDrawerOpen.value = !leftDrawerOpen.value
}
</script>
