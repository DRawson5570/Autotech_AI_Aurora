<script context="module">
  // Disable server-side rendering for this test-only page so tests can mount the component without SSR auth checks
  export const ssr = false;
</script>

<script lang="ts">
  import Billing from '$lib/components/admin/Billing.svelte';
  // This route is for local e2e testing only. Do NOT enable in production.
  // It intentionally bypasses admin guard to let tests mount the component directly.
  let loaded = true;
</script>

{#if loaded}
  <Billing />
{/if}
