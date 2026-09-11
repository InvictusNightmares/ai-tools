package requestcontent

import (
	"bufio"
	"bytes"
	"compress/gzip"
	"container/heap"
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"os"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
)

type Metadata struct {
	StoredBodyBytes    int64     `json:"stored_body_bytes"`
	RecordedAt         time.Time `json:"recorded_at"`
	RequestID          string    `json:"request_id"`
	ClientRequestID    string    `json:"client_request_id,omitempty"`
	AccountID          int64     `json:"account_id"`
	ErrorCode          string    `json:"error_code"`
	ErrorType          string    `json:"error_type,omitempty"`
	SignalPath         string    `json:"signal_path,omitempty"`
	Reason             string    `json:"reason,omitempty"`
	UpstreamRequestID  string    `json:"upstream_request_id,omitempty"`
	UpstreamResponseID string    `json:"upstream_response_id,omitempty"`
	BodyEncoding       string    `json:"body_encoding,omitempty"`
	UpstreamStatus     int       `json:"upstream_status"`
	UserID             int64     `json:"user_id"`
	APIKeyID           int64     `json:"api_key_id"`
	APIKeyName         string    `json:"api_key_name"`
	GroupID            *int64    `json:"group_id,omitempty"`
	GroupName          string    `json:"group_name,omitempty"`
	Provider           string    `json:"provider"`
	Endpoint           string    `json:"endpoint"`
	Protocol           string    `json:"protocol"`
	Model              string    `json:"model"`
	Stage              string    `json:"stage"`
	BodyBytes          int       `json:"body_bytes"`
	BodySHA256         string    `json:"body_sha256"`
	ID                 string    `json:"id"`
}

type Query struct {
	Page, PageSize        int
	Key, Model, ErrorCode string
	Start, End            time.Time
}
type Listing struct {
	Items           []Metadata `json:"items"`
	Total           int        `json:"total"`
	Page            int        `json:"page"`
	PageSize        int        `json:"page_size"`
	IndexPending    bool       `json:"index_pending"`
	IndexLimited    bool       `json:"index_limited"`
	UnreadableFiles int        `json:"unreadable_files"`
	DiskBytes       int64      `json:"disk_bytes"`
}
type indexedRecord struct {
	meta   Metadata
	name   string
	offset int64
}
type segmentIndex struct {
	info   os.FileInfo
	offset int64
	broken bool
}
type recordHeap []*indexedRecord

func (h recordHeap) Len() int { return len(h) }
func newer(a, b Metadata) bool {
	if a.RecordedAt.Equal(b.RecordedAt) {
		return a.ID > b.ID
	}
	return a.RecordedAt.After(b.RecordedAt)
}
func (h recordHeap) Less(i, j int) bool { return newer(h[j].meta, h[i].meta) }
func (h recordHeap) Swap(i, j int)      { h[i], h[j] = h[j], h[i] }
func (h *recordHeap) Push(v any)        { *h = append(*h, v.(*indexedRecord)) }
func (h *recordHeap) Pop() any {
	a := *h
	v := a[len(a)-1]
	a[len(a)-1] = nil
	*h = a[:len(a)-1]
	return v
}

// Reader keeps a rolling metadata-only index. Gzip members and downloads are
// streamed behind one shared read gate; body size never determines heap usage.
type Reader struct {
	directory string
	gate      chan struct{}
	segments  map[string]*segmentIndex
	entries   map[string]*indexedRecord
	oldest    recordHeap
	limited   bool
}

var segmentName = regexp.MustCompile(`^requests-[0-9]{8}T[0-9]{2}-[0-9]+-[0-9]+-[0-9]+\.jsonl\.gz$`)
var ErrReadBusy = errors.New("request content reader busy")

const maxIndexedRecords = 50000

// v2 permits 64 MiB before JSON HTML escaping, whose worst-case expansion is 6x.
const maxMemberBytes = 512 << 20

func NewReader(directory string) *Reader {
	return &Reader{directory: directory, gate: make(chan struct{}, 1), segments: map[string]*segmentIndex{}, entries: map[string]*indexedRecord{}}
}
func (r *Reader) lock(ctx context.Context) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	select {
	case r.gate <- struct{}{}:
		return nil
	default:
		return ErrReadBusy
	}
}
func (r *Reader) openRoot() (*os.Root, error) {
	st, err := os.Lstat(r.directory)
	if err != nil {
		return nil, err
	}
	if !st.IsDir() || st.Mode()&os.ModeSymlink != 0 {
		return nil, os.ErrPermission
	}
	return os.OpenRoot(r.directory)
}
func openSegment(root *os.Root, name string) (*os.File, error) {
	if !segmentName.MatchString(name) {
		return nil, os.ErrNotExist
	}
	before, err := root.Lstat(name)
	if err != nil {
		return nil, err
	}
	if !before.Mode().IsRegular() {
		return nil, os.ErrPermission
	}
	f, err := root.Open(name)
	if err != nil {
		return nil, err
	}
	after, err := f.Stat()
	if err != nil || !after.Mode().IsRegular() || !os.SameFile(before, after) {
		f.Close()
		return nil, os.ErrPermission
	}
	return f, nil
}

type contextReader struct {
	ctx context.Context
	r   io.Reader
}

func (r contextReader) Read(p []byte) (int, error) {
	if err := r.ctx.Err(); err != nil {
		return 0, err
	}
	return r.r.Read(p)
}

// openMember reads only the bounded metadata prefix. Entry's body is the final
// field in all recorder versions. Decode never materializes the body token.
func openMember(ctx context.Context, f *os.File, offset, size int64) (Metadata, io.Reader, func() (int64, error), error) {
	var meta Metadata
	section := io.NewSectionReader(f, offset, size-offset)
	buffer := bufio.NewReader(contextReader{ctx, section})
	z, err := gzip.NewReader(buffer)
	if err != nil {
		return meta, nil, nil, err
	}
	z.Multistream(false)
	bounded := &io.LimitedReader{R: contextReader{ctx, z}, N: maxMemberBytes + 1}
	prefix := &io.LimitedReader{R: bounded, N: 1 << 20}
	dec := json.NewDecoder(prefix)
	fail := func(err error) (Metadata, io.Reader, func() (int64, error), error) {
		z.Close()
		return meta, nil, nil, err
	}
	token, err := dec.Token()
	if err != nil {
		return fail(err)
	}
	if token != json.Delim('{') {
		return fail(errors.New("invalid record header"))
	}
	fields := map[string]json.RawMessage{}
	for {
		key, e := dec.Token()
		if e != nil {
			return fail(e)
		}
		name, ok := key.(string)
		if !ok {
			return fail(errors.New("invalid field"))
		}
		if name == "body" {
			header, _ := json.Marshal(fields)
			if e := json.Unmarshal(header, &meta); e != nil {
				return fail(e)
			}
			// Buffered bytes start after the body key. Strip its colon, and the enclosing
			// record's final }\n with a tiny rolling tail, preserving the stored body.
			bodyStart := bufio.NewReader(io.MultiReader(dec.Buffered(), bounded))
			for {
				b, e := bodyStart.ReadByte()
				if e != nil {
					return fail(e)
				}
				if b == ':' {
					break
				}
				if b != ' ' && b != '\n' && b != '\r' && b != '\t' {
					return fail(errors.New("missing body colon"))
				}
			}
			body := &suffixReader{r: bodyStart}
			finish := func() (int64, error) {
				_, e := io.Copy(io.Discard, body)
				z.Close()
				if e != nil {
					return offset, e
				}
				if bounded.N == 0 {
					return offset, errors.New("member limit exceeded")
				}
				pos, _ := section.Seek(0, io.SeekCurrent)
				return offset + pos - int64(buffer.Buffered()), nil
			}
			return meta, body, finish, nil
		}
		var value json.RawMessage
		if e := dec.Decode(&value); e != nil {
			return fail(e)
		}
		fields[name] = value
	}
}

// suffixReader removes the encoder's enclosing record suffix without retaining
// its body; checksum/truncation errors propagate from the gzip stream.
type suffixReader struct {
	r       io.Reader
	tail    []byte
	pending []byte
	done    bool
	err     error
}

func (s *suffixReader) Read(p []byte) (int, error) {
	if len(p) == 0 {
		return 0, nil
	}
	for len(s.pending) == 0 && !s.done {
		var b [32768]byte
		n, e := s.r.Read(b[:])
		data := append(s.tail, b[:n]...)
		if len(data) > 2 {
			s.pending = append(s.pending, data[:len(data)-2]...)
			s.tail = append([]byte(nil), data[len(data)-2:]...)
		} else {
			s.tail = append([]byte(nil), data...)
		}
		if e != nil {
			s.done = true
			s.err = e
			if e == io.EOF && !bytes.Equal(s.tail, []byte("}\n")) {
				s.err = io.ErrUnexpectedEOF
			}
		}
	}
	if len(s.pending) > 0 {
		n := copy(p, s.pending)
		s.pending = s.pending[n:]
		return n, nil
	}
	return 0, s.err
}
func recordID(name string, offset int64) string {
	h := sha256.New()
	h.Write([]byte(name))
	var b [8]byte
	for i := range b {
		b[i] = byte(uint64(offset) >> (8 * i))
	}
	h.Write(b[:])
	return hex.EncodeToString(h.Sum(nil))
}
func (r *Reader) index(row *indexedRecord) {
	if len(r.entries) >= maxIndexedRecords {
		r.limited = true
		if !newer(row.meta, r.oldest[0].meta) {
			return
		}
		old := heap.Pop(&r.oldest).(*indexedRecord)
		delete(r.entries, old.meta.ID)
	}
	r.entries[row.meta.ID] = row
	heap.Push(&r.oldest, row)
}
func (r *Reader) List(ctx context.Context, q Query) (Listing, error) {
	out := Listing{Items: []Metadata{}, Page: q.Page, PageSize: q.PageSize}
	if q.Page < 1 || q.PageSize < 1 || q.PageSize > 100 || q.Page > 50000 {
		return out, errors.New("invalid pagination")
	}
	if err := r.lock(ctx); err != nil {
		return out, err
	}
	defer func() { <-r.gate }()
	root, err := r.openRoot()
	if os.IsNotExist(err) {
		clear(r.segments)
		clear(r.entries)
		r.oldest = nil
		r.limited = false
		return out, nil
	}
	if err != nil {
		return out, err
	}
	defer root.Close()
	d, err := root.Open(".")
	if err != nil {
		return out, err
	}
	files, err := d.ReadDir(-1)
	d.Close()
	if err != nil {
		return out, err
	}
	live := map[string]os.FileInfo{}
	names := []string{}
	for _, f := range files {
		if !segmentName.MatchString(f.Name()) || !f.Type().IsRegular() {
			continue
		}
		info, e := f.Info()
		if e != nil {
			continue
		}
		live[f.Name()] = info
		names = append(names, f.Name())
		out.DiskBytes += info.Size()
	}
	removed := false
	for name, seg := range r.segments {
		info, ok := live[name]
		if !ok || !os.SameFile(info, seg.info) || info.Size() < seg.offset {
			delete(r.segments, name)
			removed = true
		}
	}
	if removed {
		r.oldest = nil
		for id, row := range r.entries {
			if _, ok := r.segments[row.name]; !ok {
				delete(r.entries, id)
			} else {
				r.oldest = append(r.oldest, row)
			}
		}
		heap.Init(&r.oldest)
	}
	sort.Sort(sort.Reverse(sort.StringSlice(names)))
	deadline := time.Now().Add(2 * time.Second)
	budget := int64(256 << 20)
	for _, name := range names {
		info := live[name]
		seg := r.segments[name]
		if seg == nil {
			seg = &segmentIndex{info: info}
			r.segments[name] = seg
		}
		if seg.broken {
			out.UnreadableFiles++
			continue
		}
		if seg.offset >= info.Size() {
			continue
		}
		if time.Now().After(deadline) || budget <= 0 {
			out.IndexPending = true
			continue
		}
		f, e := openSegment(root, name)
		if e != nil {
			out.UnreadableFiles++
			continue
		}
		for seg.offset < info.Size() {
			if time.Now().After(deadline) || budget <= 0 {
				out.IndexPending = true
				break
			}
			if ctx.Err() != nil {
				f.Close()
				return out, ctx.Err()
			}
			meta, body, finish, e := openMember(ctx, f, seg.offset, info.Size())
			var next int64
			var bodySize int64
			if e == nil {
				var n int64
				n, e = io.Copy(io.Discard, body)
				bodySize = n
				budget -= n
				var endErr error
				next, endErr = finish()
				if e == nil {
					e = endErr
				}
			}
			if e != nil {
				if ctx.Err() != nil {
					f.Close()
					return out, ctx.Err()
				}
				if errors.Is(e, io.ErrUnexpectedEOF) || errors.Is(e, io.EOF) {
					out.IndexPending = true
				} else {
					seg.broken = true
					out.UnreadableFiles++
				}
				break
			}
			if next <= seg.offset {
				seg.broken = true
				out.UnreadableFiles++
				break
			}
			meta.ID = recordID(name, seg.offset)
			meta.StoredBodyBytes = bodySize
			if meta.BodyEncoding == "base64" {
				meta.StoredBodyBytes = int64(meta.BodyBytes)
			}
			r.index(&indexedRecord{meta: meta, name: name, offset: seg.offset})
			seg.offset = next
		}
		f.Close()
	}
	out.IndexLimited = r.limited
	rows := []Metadata{}
	key := strings.ToLower(strings.TrimSpace(q.Key))
	model := strings.ToLower(strings.TrimSpace(q.Model))
	for _, row := range r.entries {
		m := row.meta
		if !q.Start.IsZero() && m.RecordedAt.Before(q.Start) || !q.End.IsZero() && !m.RecordedAt.Before(q.End) {
			continue
		}
		if q.ErrorCode != "" && q.ErrorCode != m.ErrorCode {
			continue
		}
		if model != "" && !strings.Contains(strings.ToLower(m.Model), model) {
			continue
		}
		if key != "" && !strings.Contains(strings.ToLower(m.APIKeyName), key) && key != strconv.FormatInt(m.APIKeyID, 10) {
			continue
		}
		rows = append(rows, m)
	}
	sort.Slice(rows, func(i, j int) bool { return newer(rows[i], rows[j]) })
	out.Total = len(rows)
	start := (q.Page - 1) * q.PageSize
	if start < len(rows) {
		out.Items = rows[start:min(start+q.PageSize, len(rows))]
	}
	return out, nil
}

// WithBody holds the shared gate until the consumer finishes, including slow
// downloads. Consumers must not retain the reader. Base64 multipart bodies are
// decoded as a stream; JSON bodies preserve the bytes in the retained file.
func (r *Reader) WithBody(ctx context.Context, id string, consume func(Metadata, io.Reader) error) error {
	if len(id) != 64 {
		return os.ErrNotExist
	}
	if _, err := hex.DecodeString(id); err != nil {
		return os.ErrNotExist
	}
	if err := r.lock(ctx); err != nil {
		return err
	}
	defer func() { <-r.gate }()
	row, ok := r.entries[id]
	if !ok {
		return os.ErrNotExist
	}
	seg := r.segments[row.name]
	root, err := r.openRoot()
	if err != nil {
		return err
	}
	defer root.Close()
	f, err := openSegment(root, row.name)
	if err != nil {
		return err
	}
	defer f.Close()
	info, err := f.Stat()
	if err != nil {
		return err
	}
	if seg == nil || !os.SameFile(info, seg.info) {
		return os.ErrNotExist
	}
	meta, body, finish, err := openMember(ctx, f, row.offset, info.Size())
	if err != nil {
		return err
	}
	defer finish()
	if meta.BodySHA256 != row.meta.BodySHA256 {
		return os.ErrNotExist
	}
	meta.ID = id
	meta.StoredBodyBytes = row.meta.StoredBodyBytes
	if meta.BodyEncoding == "base64" {
		b := bufio.NewReader(body)
		quote, e := b.ReadByte()
		if e != nil || quote != '"' {
			return errors.New("invalid encoded body")
		}
		body = base64.NewDecoder(base64.StdEncoding, &quoteReader{r: b})
	}
	if err = consume(meta, body); err != nil {
		return err
	}
	_, err = finish()
	return err
}

// Base64 strings produced by the recorder do not contain JSON escapes.
type quoteReader struct {
	r    *bufio.Reader
	done bool
}

func (r *quoteReader) Read(p []byte) (int, error) {
	if r.done {
		return 0, io.EOF
	}
	n := 0
	for n < len(p) {
		b, e := r.r.ReadByte()
		if e != nil {
			return n, e
		}
		if b == '"' {
			r.done = true
			return n, io.EOF
		}
		p[n] = b
		n++
	}
	return n, nil
}

var readerOnce sync.Once
var defaultReader *Reader

func DefaultReader() *Reader {
	readerOnce.Do(func() {
		base := os.Getenv("DATA_DIR")
		if base == "" {
			base = "/app/data"
		}
		defaultReader = NewReader(base + "/policy-requests")
	})
	return defaultReader
}

type AdminStatus struct {
	Enabled       bool   `json:"enabled"`
	RetentionDays int    `json:"retention_days"`
	MaxDiskMB     int64  `json:"max_disk_mb"`
	Runtime       Status `json:"runtime"`
}

func ReadAdminStatus() AdminStatus {
	s := AdminStatus{Enabled: Enabled()}
	if r := defaultRecorder.Load(); r != nil {
		s.RetentionDays = int(r.opts.Retention / (24 * time.Hour))
		s.MaxDiskMB = r.opts.MaxDiskBytes >> 20
		s.Runtime = r.Snapshot()
	}
	return s
}
