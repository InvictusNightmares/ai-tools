package admin

import (
	"context"
	"errors"
	"io"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/Wei-Shaw/sub2api/internal/pkg/response"
	"github.com/Wei-Shaw/sub2api/internal/requestcontent"
	"github.com/Wei-Shaw/sub2api/internal/server/middleware"
	"github.com/gin-gonic/gin"
)

// PolicyRequestsHandler exposes the local recorder through the existing admin
// boundary. It has no configuration mutations and does not invoke moderation.
type PolicyRequestsHandler struct{ reader *requestcontent.Reader }

func NewPolicyRequestsHandler(reader *requestcontent.Reader) *PolicyRequestsHandler {
	return &PolicyRequestsHandler{reader: reader}
}
func policyAdmin(c *gin.Context) bool {
	c.Header("Cache-Control", "no-store")
	c.Header("X-Content-Type-Options", "nosniff")
	role, ok := middleware.GetUserRoleFromContext(c)
	if !ok {
		response.Unauthorized(c, "Authorization required")
		return false
	}
	if role != "admin" {
		response.Forbidden(c, "Administrator access required")
		return false
	}
	return true
}
func policyReadError(c *gin.Context, err error) {
	if os.IsNotExist(err) {
		response.NotFound(c, "Record expired or no longer available; refresh the list")
		return
	}
	if errors.Is(err, requestcontent.ErrReadBusy) || errors.Is(err, context.DeadlineExceeded) {
		response.Error(c, http.StatusServiceUnavailable, "Reader is busy; retry shortly")
		return
	}
	response.InternalError(c, "Unable to read retained requests")
}
func (h *PolicyRequestsHandler) List(c *gin.Context) {
	if !policyAdmin(c) {
		return
	}
	q := requestcontent.Query{Page: 1, PageSize: 20, Key: strings.TrimSpace(c.Query("key")), Model: strings.TrimSpace(c.Query("model")), ErrorCode: c.Query("error_code")}
	for name, dst := range map[string]*int{"page": &q.Page, "page_size": &q.PageSize} {
		if s := c.Query(name); s != "" {
			n, e := strconv.Atoi(s)
			if e != nil || n < 1 || n > 50000 || name == "page_size" && n > 100 {
				response.BadRequest(c, "Invalid pagination")
				return
			}
			*dst = n
		}
	}
	if len(q.Key) > 200 || len(q.Model) > 200 || len(q.ErrorCode) > 100 {
		response.BadRequest(c, "Filter is too long")
		return
	}
	for name, dst := range map[string]*time.Time{"start_time": &q.Start, "end_time": &q.End} {
		if s := c.Query(name); s != "" {
			v, e := time.Parse(time.RFC3339, s)
			if e != nil {
				response.BadRequest(c, "Invalid time; expected RFC3339")
				return
			}
			*dst = v
		}
	}
	if !q.Start.IsZero() && !q.End.IsZero() && !q.End.After(q.Start) {
		response.BadRequest(c, "End time must be after start time")
		return
	}
	ctx, cancel := context.WithTimeout(c.Request.Context(), 5*time.Second)
	defer cancel()
	result, err := h.reader.List(ctx, q)
	if err != nil {
		policyReadError(c, err)
		return
	}
	response.Success(c, gin.H{"records": result, "status": requestcontent.ReadAdminStatus()})
}
func (h *PolicyRequestsHandler) Get(c *gin.Context) {
	if !policyAdmin(c) {
		return
	}
	ctx, cancel := context.WithTimeout(c.Request.Context(), 10*time.Second)
	defer cancel()
	var meta requestcontent.Metadata
	var preview []byte
	var truncated bool
	err := h.reader.WithBody(ctx, c.Param("id"), func(m requestcontent.Metadata, body io.Reader) error {
		meta = m
		var e error
		preview, e = io.ReadAll(io.LimitReader(body, (256<<10)+1))
		if e != nil {
			return e
		}
		truncated = len(preview) > 256<<10
		if truncated {
			preview = preview[:256<<10]
		}
		return nil
	})
	if err != nil {
		policyReadError(c, err)
		return
	}
	response.Success(c, gin.H{"record": meta, "body_preview": string(preview), "preview_truncated": truncated})
}
func (h *PolicyRequestsHandler) Download(c *gin.Context) {
	if !policyAdmin(c) {
		return
	}
	ctx, cancel := context.WithTimeout(c.Request.Context(), 30*time.Second)
	defer cancel()
	err := h.reader.WithBody(ctx, c.Param("id"), func(meta requestcontent.Metadata, body io.Reader) error {
		// Keep slow clients bounded without changing the server's global timeouts.
		control := http.NewResponseController(c.Writer)
		if e := control.SetWriteDeadline(time.Now().Add(30 * time.Second)); e != nil {
			return e
		}
		defer control.SetWriteDeadline(time.Time{})
		c.Header("Content-Disposition", `attachment; filename="policy-request-`+meta.ID[:12]+`.txt"`)
		c.Header("Content-Type", "application/octet-stream")
		// Exact length was validated while indexing; clients reject interrupted streams.
		c.Header("Content-Length", strconv.FormatInt(meta.StoredBodyBytes, 10))
		c.Status(http.StatusOK)
		_, e := io.Copy(c.Writer, body)
		return e
	})
	if err != nil && !c.Writer.Written() {
		policyReadError(c, err)
	}
}
