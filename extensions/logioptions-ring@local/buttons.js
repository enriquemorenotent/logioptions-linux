// Pure validation shared by the live D-Bus endpoint and tests.
const modifiers = new Set(['Control_L', 'Shift_L', 'Alt_L', 'Super_L']);
const desktop = new Set(['overview', 'show_desktop', 'workspace_left', 'workspace_right']);
export function validateButtonAction(action) {
    if (!action || typeof action !== 'object' || Array.isArray(action)) throw new Error('Invalid button action');
    const fields = Object.keys(action).sort().join(',');
    if (action.type === 'ring' && fields === 'type') return action;
    if (action.type === 'desktop' && fields === 'action,type' && desktop.has(action.action)) return action;
    const keys = action.keys;
    if (action.type === 'shortcut' && fields === 'keys,type' && Array.isArray(keys) && keys.length >= 1 && keys.length <= 5 &&
        new Set(keys).size === keys.length && keys.every(key => typeof key === 'string' && /^[A-Za-z0-9_]{1,64}$/.test(key)) &&
        keys.slice(0, -1).every(key => modifiers.has(key)) && !modifiers.has(keys.at(-1))) return action;
    throw new Error('Unsupported button action');
}
