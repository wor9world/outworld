export type Theme = 'system' | 'light' | 'dark';

const KEY = 'outworld-theme';

export function getTheme(): Theme {
	if (typeof localStorage === 'undefined') return 'system';
	const stored = localStorage.getItem(KEY);
	return stored === 'light' || stored === 'dark' ? stored : 'system';
}

export function applyTheme(theme: Theme): void {
	if (typeof document === 'undefined') return;
	const prefersDark =
		typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches;
	const dark = theme === 'dark' || (theme === 'system' && prefersDark);
	document.documentElement.classList.toggle('dark', dark);
}

export function setTheme(theme: Theme): void {
	localStorage.setItem(KEY, theme);
	applyTheme(theme);
}
