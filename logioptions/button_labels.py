"""Readable summaries of saved host actions and observed hardware mappings."""
from .profiles import ACTIONS
from .button_actions import DESKTOP

CONTROL_LABELS = {80:'Left click',81:'Right click',82:'Middle click',83:'Back',86:'Forward',
                  195:'Default behavior',196:'Switch wheel mode',416:'Actions Ring',215:'Default behavior'}
KEY_LABELS = {'Control_L':'Ctrl','Shift_L':'Shift','Alt_L':'Alt','Super_L':'Super',
              'Return':'Enter','KP_Enter':'Numpad Enter','space':'Space','BackSpace':'Backspace',
              'Escape':'Esc','Page_Up':'Page Up','Page_Down':'Page Down','plus':'+','minus':'−',
              'equal':'=','comma':',','period':'.','slash':'/','backslash':'\\'}


def shortcut_label(keys):
    return '+'.join(KEY_LABELS.get(key,key.upper() if len(key)==1 else key.replace('_',' ')) for key in keys)


def action_label(action):
    if action['type']=='ring': return 'Actions Ring'
    if action['type']=='desktop': return DESKTOP.get(action['action'],'Action unavailable')
    keys=action['keys']
    chord=shortcut_label(keys)
    common=next((name for name,_,candidate in ACTIONS.values() if candidate==keys),None)
    return f'{common} · {chord}' if common else chord


def assignment_label(descriptor,cid,saved):
    if str(cid) in saved:
        return action_label(saved[str(cid)])
    control=next((row for row in descriptor.get('controls',[]) if row['control_id']==cid),None)
    if not control: return 'Action unavailable'
    # The listener provides the thumb pad's default action even without a saved override.
    if cid==416 and control['flags'] & 0x20: return 'Actions Ring'
    target=control.get('reporting',{}).get('remapped_to')
    if target is None: return 'Action unavailable'
    if target==0: target=cid
    return CONTROL_LABELS.get(target,f'Button {target}')
