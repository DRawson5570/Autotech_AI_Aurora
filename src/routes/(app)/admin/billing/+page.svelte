<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import Billing from '$lib/components/admin/Billing.svelte';
  import { user } from '$lib/stores';

  let loaded = false;
  onMount(async () => {
    if ($user?.role !== 'admin') {
      await goto('/');
    }
    loaded = true;
  });
</script>

{#if loaded}
  <Billing />
{/if}
