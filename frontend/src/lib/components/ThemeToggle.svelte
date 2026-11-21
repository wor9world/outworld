<script lang="ts">
	import Sun from '@lucide/svelte/icons/sun';
	import Moon from '@lucide/svelte/icons/moon';
	import Monitor from '@lucide/svelte/icons/monitor';
	import { applyTheme, getTheme, setTheme, type Theme } from '#lib/theme.ts';

	let value = $state<Theme>('system');

	$effect(() => {
		value = getTheme();
		applyTheme(value);
	});

	const options: { id: Theme; label: string; icon: typeof Sun }[] = [
		{ id: 'system', label: 'System theme', icon: Monitor },
		{ id: 'light', label: 'Light theme', icon: Sun },
		{ id: 'dark', label: 'Dark theme', icon: Moon }
	];

	function choose(theme: Theme): void {
		value = theme;
		setTheme(theme);
	}
</script>

<div class="flex items-center gap-1" role="group" aria-label="Theme">
	{#each options as option (option.id)}
		{@const Icon = option.icon}
		<button
			type="button"
			onclick={() => choose(option.id)}
			aria-pressed={value === option.id}
			aria-label={option.label}
			title={option.label}
			class="flex size-7 items-center justify-center rounded-md text-neutral-500 hover:bg-neutral-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neutral-900 aria-pressed:bg-neutral-200 aria-pressed:text-neutral-900 dark:text-neutral-400 dark:hover:bg-neutral-800 dark:aria-pressed:bg-neutral-700 dark:aria-pressed:text-white"
		>
			<Icon size={14} strokeWidth={1.75} />
		</button>
	{/each}
</div>
