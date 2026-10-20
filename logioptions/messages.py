"""Agent request/response envelopes observed in the official 1.32 interface."""
import json


def get_request(message_id: int, path: str, payload: dict | None = None) -> bytes:
    if isinstance(message_id, bool) or not isinstance(message_id, int) or message_id < 1:
        raise ValueError('Message ID must be a positive integer')
    if not isinstance(path, str) or not path.startswith('/'):
        raise ValueError('Agent route must start with /')
    request = {'msg_id': str(message_id), 'verb': 'GET', 'path': path}
    if payload is not None:
        if not isinstance(payload, dict):
            raise ValueError('Request payload must be an object')
        request['payload'] = payload
    return json.dumps(request, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def parse_response(payload: bytes, *, message_id: int, path: str) -> dict:
    response = json.loads(payload)
    if not isinstance(response, dict):
        raise ValueError('Agent response must be an object')
    if response.get('msgId') != str(message_id) or response.get('path') != path:
        raise ValueError('Agent response does not match request')
    if response.get('verb') != 'GET':
        raise ValueError('Unexpected response verb')
    result = response.get('result')
    if not isinstance(result, dict) or not isinstance(result.get('code'), str):
        raise ValueError('Missing agent result code')
    return response
