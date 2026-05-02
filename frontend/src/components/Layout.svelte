<script>
  import Sidebar from './Sidebar.svelte';
  import Header from './Header.svelte';

  export let navigate;
  export let currentRoute;
</script>

<div class="flex h-screen bg-gray-100 dark:bg-gray-900">
  <!-- Skip to content link for keyboard/screen reader users -->
  <a href="#main-content" class="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:px-4 focus:py-2 focus:bg-blue-600 focus:text-white focus:rounded-lg">
    Skip to main content
  </a>

  <!-- Sidebar -->
  <Sidebar {navigate} {currentRoute} />

  <!-- Main content area -->
  <div class="flex flex-col flex-1 overflow-hidden">
    <Header />

    <!-- Page content -->
    <main id="main-content" class="flex-1 overflow-y-auto p-6">
      <slot />
    </main>
  </div>
</div>
