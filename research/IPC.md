# Frontend-to-agent IPC: first recovered component

Evidence: Windows and macOS offline 2.8.981479, `resources/app.asar`, extracted `main.js`.
Webpack module `2824` contains the agent framing code. The preload exposes
`electronNet` methods through Electron IPC, with a separate voice connection and
creative-console/plugin-service connection.

Observed outgoing agent frame:

| Offset | Encoding | Meaning |
| --- | --- | --- |
| 0 | uint32 little endian | Bytes following this prefix: 12 + payload length |
| 4 | uint32 big endian | Protocol name length: 4 |
| 8 | ASCII | `json` |
| 12 | uint32 big endian | Payload byte length |
| 16 | bytes | Payload |

The mixed endianness is present in the official sender. The official receiver
reads the first integer as big endian but discards it. That does **not** prove
the native agent's outgoing prefix uses the sender's little endian format.
Our decoder currently targets **frontend-originated** frames only. Native-agent
responses still need runtime evidence.

`logioptions/framing.py` implements this transport envelope. It adds a local
16 MiB limit and stricter validation; these are implementation choices, not
observed Logitech limits. It does not implement the native agent, settings
semantics, device transport or feature parity.

`python3 -m unittest discover -s tests -v` compares the Python sender with the
actual recovered Windows and macOS JavaScript factories, run with a mock socket and stub imports.
The comparison includes empty, ASCII, UTF-8 and 64 KiB payloads. Additional
checks cover fragmented/coalesced streams and malformed envelopes. This is
static differential validation, not a live Windows/macOS interoperability test.

The main bundle references the agent connection name `logitech_kiros_agent`
and rejects backend startup on operating systems other than Windows/macOS.
Reusing the Electron presentation layer alone would therefore leave the native
agent and OS integrations missing.
