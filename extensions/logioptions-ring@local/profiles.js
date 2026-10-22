// Pure selection logic, shared by the live extension and the regression checks.
export const DEFAULT = ['cut', 'copy', 'paste', 'forward', 'back', 'undo', 'redo', 'none'];
export function selectProfile(config, appId, wmClass, catalog) {
    const valid = slots => Array.isArray(slots) && slots.length === 8 &&
        slots.every(id => typeof id === 'string' && Object.hasOwn(catalog, id));
    const defaults = config?.version === 1 && valid(config.default) ? config.default : DEFAULT;
    const apps = config?.version === 1 ? config.applications : null;
    // Desktop application IDs are exact and preferred. WM_CLASS is a fallback
    // for apps which GNOME cannot associate with a desktop launcher.
    const key = appId && Object.hasOwn(apps ?? {}, appId) ? appId : `wmclass:${wmClass ?? ''}`;
    const profile = Object.hasOwn(apps ?? {}, key) ? apps[key] : null;
    const matched = profile && valid(profile.slots);
    return {name: matched && typeof profile.name === 'string' ? profile.name : 'All apps',
        slots: matched ? profile.slots : defaults};
}
