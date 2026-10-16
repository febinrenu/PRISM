/** Shared by the theme store and the root layout's pre-paint script (no client code here). */
export const THEME_KEY = "prism-theme";

/** Runs before first paint, so a light choice never flashes dark. */
export const THEME_SCRIPT = `try{var t=localStorage.getItem("${THEME_KEY}");if(t==="light"){document.documentElement.dataset.theme="light";document.documentElement.style.colorScheme="light"}}catch(e){}`;
