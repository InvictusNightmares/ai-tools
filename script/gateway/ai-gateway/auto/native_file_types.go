package autogateway

import (
	"net/http"
	"path/filepath"
	"strings"
)

// net/http detects OOXML containers as zip and adds charset to plain text.
// Native file inputs need their document MIME type, not the container type.
var nativeFileMIMEs = map[string]string{
	".pdf": "application/pdf", ".txt": "text/plain", ".md": "text/markdown", ".csv": "text/csv", ".json": "application/json", ".html": "text/html", ".xml": "application/xml",
	".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".doc": "application/msword",
	".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xls": "application/vnd.ms-excel",
	".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation", ".ppt": "application/vnd.ms-powerpoint",
	".rtf": "application/rtf", ".odt": "application/vnd.oasis.opendocument.text", ".ods": "application/vnd.oasis.opendocument.spreadsheet",
}

func nativeFileMIME(name string, data []byte) string {
	if typ := nativeFileMIMEs[strings.ToLower(filepath.Ext(name))]; typ != "" {
		return typ
	}
	return strings.TrimSpace(strings.SplitN(http.DetectContentType(data), ";", 2)[0])
}
func nativeDocumentFilename(source map[string]any) string {
	if filename := textField(source, "filename"); filename != "" {
		return filename
	}
	media := strings.ToLower(strings.TrimSpace(strings.SplitN(textField(source, "media_type"), ";", 2)[0]))
	for ext, typ := range nativeFileMIMEs {
		if media == typ {
			return "attachment" + ext
		}
	}
	return "attachment"
}
