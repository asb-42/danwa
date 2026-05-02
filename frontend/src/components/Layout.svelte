<script>
  import Sidebar from './Sidebar.svelte';
  import Header from './Header.svelte';

  export let navigate;
  export let currentRoute;
</script>

<div class="flex h-screen bg-gray-100 dark:bg-gray-900">
  <!-- Sidebar -->
  <Sidebar {navigate} {currentRoute} />

  <!-- Main content area -->
  <div class="flex flex-col flex-1 overflow-hidden">
    <Header />

    <!-- Page content -->
    <main class="flex-1 overflow-y-auto p-6">
      <slot />
    </main>
  </div>
</div>
