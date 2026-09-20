package capture

import (
	"bytes"
	"compress/flate"
	"encoding/binary"
	"encoding/json"
	"errors"
	"io"
	"strings"
)

// Passive decoder: never negotiates, rewrites or sends WebSocket frames.
// Compression follows RFC7692; only decoded observation copies are processed.
type wsDecoder struct {
	buf, fragment, dict        []byte
	opcode                     byte
	compressed                 bool
	limit                      int64
	deflate, noContext, masked bool
	invalid                    bool
}

func newWSDecoder(extensions string, request bool, limit int64) *wsDecoder {
	d := &wsDecoder{limit: limit, masked: request}
	for _, extension := range strings.Split(extensions, ",") {
		parts := strings.Split(strings.TrimSpace(extension), ";")
		if parts[0] == "" {
			continue
		}
		if strings.TrimSpace(parts[0]) != "permessage-deflate" {
			d.invalid = true
			continue
		}
		d.deflate = true
		for _, p := range parts[1:] {
			p = strings.TrimSpace(p)
			if p == "client_no_context_takeover" && request || p == "server_no_context_takeover" && !request {
				d.noContext = true
			}
		}
	}
	return d
}
func (d *wsDecoder) held() int64 { return int64(len(d.buf) + len(d.fragment)) }
func (d *wsDecoder) feed(p []byte, emit func([]byte, bool) error) error {
	if d.invalid {
		return errors.New("websocket_capture_invalid")
	}
	if len(d.buf) == 0 {
		// The caller retains this chunk until feed returns. Any unfinished
		// remainder is copied before returning, so pooled wire bytes can be reused.
		d.buf = p
	} else {
		d.buf = append(d.buf, p...)
	}
	for len(d.buf) >= 2 {
		first, second := d.buf[0], d.buf[1]
		fin := first&0x80 != 0
		compressed := first&0x40 != 0
		opcode := first & 15
		if first&0x30 != 0 || compressed && !d.deflate || second&0x80 != 0 != d.masked {
			return errors.New("websocket_frame_flags")
		}
		n := uint64(second & 127)
		offset := 2
		if n == 126 {
			if len(d.buf) < 4 {
				break
			}
			n = uint64(binary.BigEndian.Uint16(d.buf[2:4]))
			offset = 4
		} else if n == 127 {
			if len(d.buf) < 10 {
				break
			}
			n = binary.BigEndian.Uint64(d.buf[2:10])
			offset = 10
		}
		if n > uint64(d.limit) {
			return errors.New("websocket_message_limit")
		}
		masked := second&0x80 != 0
		var mask []byte
		if masked {
			if len(d.buf) < offset+4 {
				break
			}
			mask = d.buf[offset : offset+4]
			offset += 4
		}
		if len(d.buf) < offset+int(n) {
			break
		}
		payload := d.buf[offset : offset+int(n)]
		if opcode >= 8 {
			if !fin || compressed || n > 125 {
				return errors.New("invalid_websocket_control")
			}
			d.buf = d.buf[offset+int(n):]
			continue
		}
		if opcode != 0 && opcode != 1 && opcode != 2 {
			return errors.New("unsupported_websocket_opcode")
		}
		if opcode == 0 {
			if d.opcode == 0 || compressed {
				return errors.New("invalid_websocket_continuation")
			}
		} else {
			if d.opcode != 0 {
				return errors.New("interleaved_websocket_message")
			}
			d.opcode = opcode
			d.compressed = compressed
		}
		if int64(len(d.fragment))+int64(n) > d.limit {
			return errors.New("websocket_message_limit")
		}
		// Server-to-client data frames are normally unmasked. For a complete,
		// uncompressed message this payload is valid until emit returns, so pass
		// it through without a second message-sized copy. Masked or fragmented
		// frames still use the owned fragment buffer below.
		var direct []byte
		if fin && len(d.fragment) == 0 && !d.compressed {
			direct = payload
			if masked {
				// The wire buffer belongs to this decoder job and is released only
				// after emit returns, so unmask in place for a complete frame.
				for i := range direct {
					direct[i] ^= mask[i%4]
				}
			}
		} else {
			old := len(d.fragment)
			d.fragment = append(d.fragment, payload...)
			if masked {
				for i := 0; i < int(n); i++ {
					d.fragment[old+i] ^= mask[i%4]
				}
			}
		}
		d.buf = d.buf[offset+int(n):]
		if fin {
			body := d.fragment
			if direct != nil {
				body = direct
			}
			if d.compressed {
				// Restore sync-flush tail, then an empty final block to terminate Go flate.
				input := io.MultiReader(bytes.NewReader(body), bytes.NewReader([]byte{0, 0, 255, 255, 1, 0, 0, 255, 255}))
				rd := flate.NewReaderDict(input, d.dict)
				decoded, err := io.ReadAll(io.LimitReader(rd, d.limit+1))
				rd.Close()
				if err != nil || int64(len(decoded)) > d.limit {
					return errors.New("websocket_deflate_incomplete")
				}
				body = decoded
				if !d.noContext {
					joined := append(d.dict, body...)
					if len(joined) > 32768 {
						joined = joined[len(joined)-32768:]
					}
					d.dict = bytes.Clone(joined)
				} else {
					d.dict = nil
				}
			}
			if err := emit(body, d.opcode == 2); err != nil {
				return err
			}
			d.fragment = nil
			d.opcode = 0
			d.compressed = false
		}
	}
	if len(d.buf) == 0 {
		d.buf = nil
	} else {
		d.buf = bytes.Clone(d.buf)
	}
	return nil
}

type wsState struct {
	owner             *Exchange
	request, response *wsDecoder
	sequence          uint64
	failed            bool
}

func (e *Engine) wire(j job) {
	defer releaseWireBuffer(j.wireBuffer)
	if j.owner != nil {
		defer j.owner.pendingWire.Add(-1)
	}
	state := e.ws[j.event.ID]
	if state == nil {
		state = &wsState{owner: j.owner, request: newWSDecoder(j.event.WebsocketExtensions, true, e.limits.BodyBytes), response: newWSDecoder(j.event.WebsocketExtensions, false, e.limits.BodyBytes)}
		e.ws[j.event.ID] = state
	}
	if state.failed {
		e.metrics.queued.Add(-j.held)
		return
	}
	decoder := state.request
	if j.wireResponse {
		decoder = state.response
	}
	before := decoder.held()
	err := decoder.feed(j.wireData, func(raw []byte, binary bool) error {
		state.sequence++
		event := j.event
		event.ID = event.ID + "-ws-" + fmtSequence(state.sequence)
		event.Kind = "websocket_message"
		event.ConnectionID = j.event.ID
		event.Sequence = state.sequence
		event.DurationMS = -1
		event.FirstByteMS = -1
		event.Request = nil
		event.Response = nil
		event.Outcome = "observed"
		event.At = j.wireAt
		event.Direction = "request"
		if j.wireResponse {
			event.Direction = "response"
		}
		var body json.RawMessage
		var gaps []string
		if binary {
			body, _ = json.Marshal(map[string]any{"omitted": "websocket_binary", "bytes": len(raw), "sha256": digest(raw)})
		} else {
			body, gaps = ProjectBody(raw, "application/json", "", event.Path, e.limits.BodyBytes)
		}
		event.Missing = append(event.Missing, gaps...)
		if len(gaps) > 0 {
			e.metrics.projectionErrors.Add(1)
		}
		if j.wireResponse {
			event.Response = body
			event.ResponseBytes = int64(len(raw))
			event.ResponseSHA = digest(raw)
		} else {
			event.Request = body
			event.RequestBytes = int64(len(raw))
			event.RequestSHA = digest(raw)
		}
		if err := e.sink.Write(event); err != nil {
			e.metrics.writeErrors.Add(1)
			e.loss(event, "websocket_record_write_failed")
		} else {
			e.metrics.written.Add(1)
		}
		return nil
	})
	after := decoder.held()
	e.metrics.queued.Add(-(j.held + before - after))
	if err != nil {
		state.failed = true
		e.metrics.projectionErrors.Add(1)
		e.loss(j.event, "websocket_decode_incomplete")
		e.metrics.queued.Add(-(state.request.held() + state.response.held()))
		state.request.buf = nil
		state.request.fragment = nil
		state.response.buf = nil
		state.response.fragment = nil
	}
	e.metrics.stored.Store(e.sink.StoredBytes())
}
