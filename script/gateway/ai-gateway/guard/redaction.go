package gocheck

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"regexp"
	"sort"
	"strings"
)

const RedactionVersion = "credential-redaction-v1"
const redactedSecret = "<REDACTED:secret>"

const credentialName = `(?:api[_ -]?key|access[_ -]?token|refresh[_ -]?token|id[_ -]?token|client[_ -]?secret|password|passwd|private[_ -]?key|authorization|proxy-authorization|cookie|set-cookie|密码|口令|密钥)`
const quotedTemplate = "`(?:\\\\.|[^`\\\\])*`"
const authTemplate = `(?:bearer|basic)[\t ]+(?:\{[a-z_][a-z0-9_]*\}|\$\{[a-z_][a-z0-9_]*\}|<REDACTED:[^>]+>)`

var (
	credentialKey        = regexp.MustCompile(`(?i)^` + credentialName + `$`)
	credentialAssignment = regexp.MustCompile(`(?i)(["']?` + credentialName + `["']?(?::[\t ]*String\??[\t ]*)?\s*[:=]\s*)("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|` + quotedTemplate + `|` + authTemplate + `|<REDACTED:[^>]+>|\$\{[^}]+\}|[^\s,;"'}]+)`)
	credentialHeader     = regexp.MustCompile(`(?im)(\b(?:cookie|set-cookie|authorization|proxy-authorization)\s*:\s*)([^\r\n]+)`)
	authTemplateOnly     = regexp.MustCompile(`(?i)^` + authTemplate + `\.?$`)
	authSecret           = regexp.MustCompile(`(?i)\bbearer\s+[a-z0-9._~+/=-]{8,}`)
	basicSecret          = regexp.MustCompile(`(?i)\bbasic\s+([a-z0-9+/]+={0,2})`)
	knownSecret          = regexp.MustCompile(`(?i)\b(?:(?:sk-|gh[pousr]_|ghp-|xox[bpars]-)[a-z0-9_-]{12,}|github_pat_[a-z0-9_]{12,}|eyJ[a-z0-9_-]+\.[a-z0-9_-]+\.[a-z0-9_-]+)\b`)
	privateKey           = regexp.MustCompile(`(?s)-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----.*?-----END (?:[A-Z0-9]+ )*PRIVATE KEY-----`)
	credentialURL        = regexp.MustCompile(`(?i)\b([a-z][a-z0-9+.-]*://)[^\s/@:]+:[^\s/@]+@`)
)

func credentialField(key string) bool { return credentialKey.MatchString(key) }

func safeSecretReference(value string) bool {
	value = strings.TrimSpace(value)
	return value == "" || (strings.HasPrefix(value, "<REDACTED:") && strings.HasSuffix(value, ">")) ||
		(strings.HasPrefix(value, "${") && strings.HasSuffix(value, "}")) || authTemplateOnly.MatchString(value)
}

// Walk JSON values instead of applying regular expressions to encoded JSON.
// Leave unchanged payloads byte-identical; retain numbers without float rounding.
// Embedded tool arguments/config JSON are inspected recursively too.
func redactSecretText(text string) string { return redactTextDepth(text, 0) }

func redactTextDepth(text string, depth int) string {
	if depth > 32 {
		// Refuse to pass uninspected nested encodings through the boundary.
		return redactedSecret
	}
	if json.Valid([]byte(text)) {
		decoder := json.NewDecoder(strings.NewReader(text))
		decoder.UseNumber()
		var value any
		if decoder.Decode(&value) == nil {
			value, changed := redactValue(value, depth+1)
			if !changed {
				return text
			}
			var output bytes.Buffer
			encoder := json.NewEncoder(&output)
			encoder.SetEscapeHTML(false)
			if encoder.Encode(value) == nil {
				return strings.TrimSuffix(output.String(), "\n")
			}
		}
	}
	text = privateKey.ReplaceAllString(text, redactedSecret)
	text = credentialURL.ReplaceAllString(text, `${1}<REDACTED:secret>@`)
	text = credentialHeader.ReplaceAllStringFunc(text, func(match string) string {
		parts := credentialHeader.FindStringSubmatch(match)
		if safeSecretReference(parts[2]) {
			return match
		}
		return parts[1] + redactedSecret
	})
	text = replaceCredentialAssignments(text)
	text = authSecret.ReplaceAllString(text, `<REDACTED:token>`)
	text = basicSecret.ReplaceAllStringFunc(text, func(match string) string {
		// RFC 7617 encodes user-id:password, not any word following "basic".
		// Also recognize unpadded credentials and short pairs such as u:p.
		token := basicSecret.FindStringSubmatch(match)[1]
		decoded, err := base64.StdEncoding.Strict().DecodeString(token)
		if err != nil {
			decoded, err = base64.RawStdEncoding.Strict().DecodeString(token)
		}
		if err != nil || !bytes.ContainsRune(decoded, ':') {
			return match
		}
		for _, char := range decoded {
			if char < 0x20 || char == 0x7f {
				return match
			}
		}
		return "<REDACTED:token>"
	})
	return redactKnownTokens(text)
}

var codeMemberReference = regexp.MustCompile(`^[A-Za-z_$][A-Za-z0-9_$]*(?:\??\.[A-Za-z_$][A-Za-z0-9_$]*)+$`)
var codeTypeContainer = regexp.MustCompile(`(?:interface|type)\s+[A-Za-z_$][A-Za-z0-9_$]*(?:\s*=)?\s*\{[^}]*$`)
var codeSearchFile = regexp.MustCompile(`(?m)^[^\r\n]+\.(?:ets|tsx?|jsx?):\s*$`)
var codeSearchLine = regexp.MustCompile(`^\s*Line\s+[0-9]+:\s*$`)
var kotlinDeclarationPrefix = regexp.MustCompile(`\b(?:val|var)[\t ]+$`)
var kotlinRuntimeReference = regexp.MustCompile(`^[A-Za-z_$][A-Za-z0-9_$]*(?:\??\.[A-Za-z_$][A-Za-z0-9_$]*(?:\(\))?)+$`)
var kotlinFunctionParameters = regexp.MustCompile(`\bfun[\t ]+(?:[A-Za-z_$][A-Za-z0-9_$]*\.)*[A-Za-z_$][A-Za-z0-9_$]*[\t ]*\([^(){}]*$`)
var kotlinParameterAnnotation = regexp.MustCompile(`^(?i:` + credentialName + `)[\t ]*:[\t ]*(String\??)\s*[,)]`)
var credentialPlaceholderComparison = regexp.MustCompile(`(?i)^["']?` + credentialName + `["']?[\t ]*={2,3}[\t ]*(?:null|undefined|nil|true|false)(?:$|[\s),;}\]\x60])`)

func replaceCredentialAssignments(text string) string {
	var out strings.Builder
	last := 0
	for search := 0; search < len(text); {
		indexes := credentialAssignment.FindStringSubmatchIndex(text[search:])
		if indexes == nil {
			break
		}
		for i := range indexes {
			indexes[i] += search
		}
		start, end := indexes[0], indexes[1]
		search = end
		// A String parameter inside a visible Kotlin function signature supplies
		// only a type. Resume at the type's end: the broad assignment match can
		// also consume punctuation and a following credential without whitespace.
		if annotation := kotlinParameterAnnotation.FindStringSubmatchIndex(text[start:]); annotation != nil && kotlinFunctionParameters.MatchString(text[:start]) {
			search = start + annotation[3]
			continue
		}
		// Equality with a null/boolean keyword supplies no credential value.
		// Do not mistake the first '=' in 'accessToken == null' for assignment.
		// A closing Markdown backtick also terminates the keyword in documentation.
		// Literal comparisons and later assignments are still inspected normally.
		if credentialPlaceholderComparison.MatchString(text[start:]) {
			continue
		}
		// Match complete field identifiers, consistently with credentialField's
		// JSON-key handling. Native review policy uses user_authorization, which
		// is an assessment enum and must not be mistaken for Authorization.
		if start > 0 {
			previous := text[start-1]
			if previous == '_' || previous >= 'a' && previous <= 'z' || previous >= 'A' && previous <= 'Z' || previous >= '0' && previous <= '9' {
				continue
			}
		}
		prefix, raw := text[indexes[2]:indexes[3]], text[indexes[4]:indexes[5]]
		value, quote := raw, ""
		if len(value) >= 2 && strings.ContainsRune("\"'`", rune(value[0])) && value[len(value)-1] == value[0] {
			quote, value = value[:1], value[1:len(value)-1]
		}
		safe := safeSecretReference(value)
		if quote == "" {
			tail := strings.TrimLeft(text[end:], " \t")
			// Kotlin val/var declarations refer to runtime values, not a supplied
			// credential. Limit this to member chains and zero-argument calls;
			// literals, call arguments, and concatenation still require redaction.
			if kotlinDeclarationPrefix.MatchString(text[:start]) && (tail == "" || strings.ContainsRune("\r\n,;)", rune(tail[0]))) {
				if kotlinRuntimeReference.MatchString(value) || value == "null" ||
					(strings.HasSuffix(strings.TrimSpace(prefix), ":") && (value == "String" || value == "String?")) {
					safe = true
				}
			}
			// A member expression with an explicit fallback is source code, unlike
			// an unquoted dotted password in a config file. Optional access likewise
			// names a runtime value; the value itself is not present in this text.
			if codeMemberReference.MatchString(value) && (strings.Contains(value, "?.") || strings.HasPrefix(tail, "??") || strings.HasPrefix(tail, "?:") || strings.HasPrefix(value, "process.env.")) {
				safe = true
			}
			// Primitive annotations are only exempt inside a visible type container;
			// a bare password: string configuration is still credential material.
			if strings.Contains(prefix, ":") && (value == "string" || value == "string[]") && codeTypeContainer.MatchString(text[:start]) {
				safe = true
			}
			// Search tools can return an annotated member without the surrounding
			// interface. Require both a source-file heading and a Line N prefix;
			// quoted values and configuration entries remain credentials.
			if strings.Contains(prefix, ":") && (value == "string" || value == "string[]") {
				lineStart := strings.LastIndex(text[:start], "\n") + 1
				lineEnd := strings.IndexByte(text[end:], '\n')
				if lineEnd < 0 {
					lineEnd = len(text) - end
				}
				tail := strings.TrimSpace(text[end : end+lineEnd])
				if (tail == "" || tail == ";") && codeSearchLine.MatchString(text[lineStart:start]) && codeSearchFile.MatchString(text[:lineStart]) {
					safe = true
				}
			}
		}
		out.WriteString(text[last:start])
		if safe {
			out.WriteString(text[start:end])
		} else {
			out.WriteString(prefix + quote + redactedSecret + quote)
		}
		last = end
	}
	if last == 0 {
		return text
	}
	out.WriteString(text[last:])
	return out.String()
}

// A regexp word boundary includes '-' and '/'. Those are also valid inside
// opaque base64/url-safe signatures, so a random internal prefix is not a
// standalone credential. Explicit credential fields are handled separately.
func redactKnownTokens(text string) string {
	var result strings.Builder
	last := 0
	for _, match := range knownSecret.FindAllStringIndex(text, -1) {
		start, end := match[0], match[1]
		if start > 0 && strings.ContainsRune("-_/+", rune(text[start-1])) {
			continue
		}
		result.WriteString(text[last:start])
		result.WriteString("<REDACTED:token>")
		last = end
	}
	if last == 0 {
		return text
	}
	result.WriteString(text[last:])
	return result.String()
}

func redactValue(value any, depth int) (any, bool) {
	changed := false
	switch node := value.(type) {
	case map[string]any:
		for key, old := range node {
			if text, ok := old.(string); ok && credentialField(key) && !safeSecretReference(text) {
				node[key], changed = redactedSecret, true
				continue
			}
			fresh, different := redactValue(old, depth)
			node[key], changed = fresh, changed || different
		}
	case []any:
		for i, old := range node {
			fresh, different := redactValue(old, depth)
			node[i], changed = fresh, changed || different
		}
	case string:
		fresh := redactTextDepth(node, depth)
		return fresh, fresh != node
	}
	return value, changed
}

func normalizedSafetyText(input SafetyInput) string {
	var builder strings.Builder
	builder.WriteString(input.ProviderPayload)
	builder.WriteByte('\n')
	for _, message := range input.Messages {
		builder.WriteString(message.Role)
		builder.WriteByte(':')
		builder.WriteString(message.Content)
		builder.WriteByte('\n')
	}
	for _, tool := range input.Tools {
		builder.WriteString("tool:")
		builder.WriteString(tool.Name)
		builder.WriteByte(':')
		builder.WriteString(tool.Schema)
		builder.WriteByte('\n')
	}
	for _, attachment := range input.Attachments {
		builder.WriteString("attachment:")
		builder.WriteString(attachment.Type)
		builder.WriteByte(':')
		builder.WriteString(attachment.Source)
		builder.WriteByte('\n')
	}
	keys := make([]string, 0, len(input.Metadata))
	for key := range input.Metadata {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	for _, key := range keys {
		builder.WriteString("metadata:")
		builder.WriteString(key)
		builder.WriteByte(':')
		builder.WriteString(input.Metadata[key])
		builder.WriteByte('\n')
	}
	return builder.String()
}

var secretUseMarker = regexp.MustCompile(`(?i)(send|share|extract|steal|verify|validate|replay|login|authenticate|use\s+(?:this|the)|发送|分享|提取|窃取|验证|登录|认证|使用这个|用这个)`)

// SanitizeInputForModel returns an independent copy for Guard and auditing.
func SanitizeInputForModel(input SafetyInput) SafetyInput {
	result := input
	result.ProviderPayload = redactSecretText(input.ProviderPayload)
	result.Messages = append([]SafetyMessage(nil), input.Messages...)
	for i := range result.Messages {
		result.Messages[i].Content = redactSecretText(result.Messages[i].Content)
	}
	result.Tools = append([]SafetyTool(nil), input.Tools...)
	for i := range result.Tools {
		result.Tools[i].Name = redactSecretText(result.Tools[i].Name)
		result.Tools[i].Schema = redactSecretText(result.Tools[i].Schema)
	}
	result.Attachments = append([]SafetyAttachment(nil), input.Attachments...)
	for i := range result.Attachments {
		result.Attachments[i].Source = redactSecretText(result.Attachments[i].Source)
	}
	result.Metadata = make(map[string]string, len(input.Metadata))
	for key, value := range input.Metadata {
		if credentialField(key) && !safeSecretReference(value) {
			result.Metadata[key] = redactedSecret
		} else {
			result.Metadata[key] = redactSecretText(value)
		}
	}
	if len(input.RawBody) > 0 {
		result.RawBody = []byte(redactSecretText(string(input.RawBody)))
	}
	return result
}

func containsSecret(input SafetyInput) bool {
	return normalizedSafetyText(input) != normalizedSafetyText(SanitizeInputForModel(input))
}
