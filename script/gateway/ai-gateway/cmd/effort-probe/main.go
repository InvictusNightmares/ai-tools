// effort-probe checks provider acceptance, not Auto/Guard end-to-end behavior.
package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	ag "local/ai-gateway/auto"
	"net/http"
	"net/url"
	"os"
	"strings"
	"sync"
	"time"
)

type job struct {
	Model              ag.Model
	Protocol, Language string
	Effort             ag.ReasoningEffort
}

func main() {
	base := flag.String("base-url", "", "authorized regional /v1 URL")
	tokenFile := flag.String("token-file", "", "private token file")
	out := flag.String("out", "", "new metadata-only JSONL output")
	parallel := flag.Int("parallel", 3, "concurrency 1..4")
	protocolFlag := flag.String("protocols", "chat,responses", "comma separated chat,responses,anthropic")
	direct := flag.Bool("direct-provider-probe", false, "acknowledge this does not run Guard or Auto routing")
	flag.Parse()
	protocols := strings.Split(*protocolFlag, ",")
	for _, p := range protocols {
		if p != "chat" && p != "responses" && p != "anthropic" {
			fatal("invalid protocol")
		}
	}
	u, err := url.Parse(*base)
	if err != nil || u.Host == "" || u.User != nil || u.RawQuery != "" || (u.Scheme != "http" && u.Scheme != "https") || !*direct || *parallel < 1 || *parallel > 4 {
		fatal("invalid probe parameters")
	}
	info, err := os.Stat(*tokenFile)
	if err != nil || info.Mode().Perm()&0077 != 0 {
		fatal("token file must be private")
	}
	token, err := os.ReadFile(*tokenFile)
	if err != nil {
		fatal("cannot read token file")
	}
	f, err := os.OpenFile(*out, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
	if err != nil {
		fatal("output must be a new file")
	}
	defer f.Close()
	client := &http.Client{Timeout: 60 * time.Second, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
	prompts := map[string]string{
		"zh":    "只给出 Go 布尔表达式：变量 n 是大于零的偶数。不要解释。",
		"en":    "Give only the Go boolean expression: variable n is a positive even integer. No explanation.",
		"mixed": "只返回 Go boolean expression：n is positive and even，不要解释。",
	}
	jobs := make(chan job)
	var wg sync.WaitGroup
	var mu sync.Mutex
	for i := 0; i < *parallel; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := range jobs {
				started := time.Now()
				id := fmt.Sprintf("effort-%d-%s", started.UnixNano(), j.Language)
				envelope := map[string]any{"model": "auto", "reasoning_effort": "low", "reasoning": map[string]any{"effort": "low"}}
				path := "/chat/completions"
				if j.Protocol == "responses" {
					envelope["input"] = prompts[j.Language]
					envelope["max_output_tokens"] = 1024
					path = "/responses"
				} else {
					envelope["messages"] = []map[string]string{{"role": "user", "content": prompts[j.Language]}}
					envelope["max_tokens"] = 1024
					if j.Protocol == "anthropic" {
						path = "/messages"
					}
				}
				raw, _ := json.Marshal(envelope)
				normalized, err := ag.NormalizeProtocolRequest(j.Protocol, raw)
				if err != nil {
					fatal("normalization failed")
				}
				parameters := ag.BuildProviderParameters(j.Model.Provider, j.Protocol, j.Model, j.Effort, false)
				payload, err := ag.BuildProviderPayload(j.Protocol, normalized, parameters)
				if err != nil {
					fatal("payload failed")
				}
				req, _ := http.NewRequest("POST", strings.TrimRight(*base, "/")+path, bytes.NewReader(payload))
				req.Header.Set("Authorization", "Bearer "+strings.TrimSpace(string(token)))
				req.Header.Set("Content-Type", "application/json")
				req.Header.Set("X-Request-ID", id)
				if j.Protocol == "anthropic" {
					req.Header.Set("anthropic-version", "2023-06-01")
				}
				record := map[string]any{"scope": "direct_provider_not_guard_auto", "request_id": id, "at": started.UTC(), "language": j.Language, "protocol": j.Protocol, "requested_model": j.Model.Name, "generated_target": j.Effort, "wire_reasoning": parameters.ReasoningParameter, "applied_effort": parameters.Reasoning.Applied, "mapping_status": parameters.Reasoning.Status, "http_status": 0, "complete": false}
				res, callErr := client.Do(req)
				if callErr != nil {
					record["error"] = "transport_error"
				} else {
					record["http_status"] = res.StatusCode
					record["upstream_request_id"] = res.Header.Get("X-Request-ID")
					data, readErr := io.ReadAll(io.LimitReader(res.Body, 2*1024*1024+1))
					res.Body.Close()
					record["response_sha256"] = fmt.Sprintf("%x", sha256.Sum256(data))
					var response map[string]any
					if readErr != nil || len(data) > 2*1024*1024 || json.Unmarshal(data, &response) != nil {
						record["error"] = "invalid_response"
					} else {
						record["response_model"], record["response_id"], record["usage"] = response["model"], response["id"], response["usage"]
						if r, ok := response["reasoning"].(map[string]any); ok {
							record["response_reported_effort"] = r["effort"]
						}
						complete := false
						if j.Protocol == "responses" {
							complete = response["status"] == "completed"
							record["response_status"] = response["status"]
						} else if j.Protocol == "anthropic" {
							record["finish_reason"] = response["stop_reason"]
							complete = response["type"] == "message" && response["stop_reason"] == "end_turn"
						} else if choices, ok := response["choices"].([]any); ok && len(choices) > 0 {
							if first, ok := choices[0].(map[string]any); ok {
								record["finish_reason"] = first["finish_reason"]
								complete = first["finish_reason"] == "stop"
							}
						}
						record["complete"] = res.StatusCode == 200 && complete && response["id"] != nil && response["model"] == j.Model.Name && response["error"] == nil
						if response["error"] != nil {
							record["error"] = "provider_error"
						}
					}
				}
				record["latency_ms"] = time.Since(started).Milliseconds()
				mu.Lock()
				if json.NewEncoder(f).Encode(record) != nil || f.Sync() != nil {
					fatal("evidence write failed")
				}
				fmt.Printf("model=%s protocol=%s effort=%s lang=%s status=%v complete=%v\n", j.Model.Name, j.Protocol, j.Effort, j.Language, record["http_status"], record["complete"])
				mu.Unlock()
			}
		}()
	}
	for _, model := range ag.DefaultCatalog {
		for _, protocol := range protocols {
			for _, effort := range model.ReasoningEfforts {
				for _, language := range []string{"zh", "en", "mixed"} {
					jobs <- job{model, protocol, language, effort}
				}
			}
		}
	}
	close(jobs)
	wg.Wait()
}
func fatal(message string) { fmt.Fprintln(os.Stderr, message); os.Exit(1) }
