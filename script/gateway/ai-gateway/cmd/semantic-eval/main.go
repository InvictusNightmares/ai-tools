// semantic-eval measures real classifier responses. It never calls a business
// model and cannot be used as end-to-end Guard/Auto acceptance evidence.
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	ag "local/ai-gateway/auto"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"
)

type fixture struct {
	Cases []struct {
		ID         string                     `json:"id"`
		Source     string                     `json:"source"`
		Split      string                     `json:"split"`
		Expected   string                     `json:"expected_task"`
		Complexity string                     `json:"reviewer_complexity"`
		Protocol   string                     `json:"protocol"`
		Variants   map[string]json.RawMessage `json:"variants"`
	} `json:"cases"`
}
type sample struct {
	ID, Lang, Source, Split, Expected, Complexity, Protocol string
	Body                                                    json.RawMessage
}

func main() {
	cases := flag.String("cases", "", "fixture JSON path")
	endpoint := flag.String("endpoint", "", "fixed classifier Chat URL")
	primary := flag.String("primary", "", "candidate classifier")
	reviewer := flag.String("reviewer", "", "independent reviewer")
	tokenFile := flag.String("token-file", "", "0600 token file; never printed")
	out := flag.String("out", "", "redacted JSONL evidence path")
	parallel := flag.Int("parallel", 3, "concurrent samples")
	limit := flag.Int("limit", 0, "sample limit (0 all)")
	split := flag.String("split", "", "fixture split")
	region := flag.String("region", "tokyo", "region recorded for this evaluation")
	keyID := flag.String("key-id", "unattributed:evaluation", "verified gateway identity; never infer a database Key ID")
	guard := flag.String("guard-url", "", "optional real input preflight URL")
	isolated := flag.Bool("classification-only", false, "explicitly test classifier in isolation; not Guard/Auto acceptance")
	flag.Parse()
	if *cases == "" || *out == "" || *endpoint == "" || *primary == "" || *reviewer == "" || (*guard == "" && !*isolated) || *parallel < 1 || *parallel > 16 || *limit < 0 || *region == "" || *keyID == "" {
		fatal("required parameters missing")
	}
	raw, err := os.ReadFile(*cases)
	if err != nil {
		fatal("cannot read fixture")
	}
	var f fixture
	if json.Unmarshal(raw, &f) != nil {
		fatal("invalid fixture")
	}
	token, err := os.ReadFile(*tokenFile)
	if err != nil {
		fatal("cannot read token")
	}
	file, err := os.OpenFile(*out, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
	if err != nil {
		fatal("evidence path must be new")
	}
	defer file.Close()
	var mu sync.Mutex
	encoder := json.NewEncoder(file)
	jobs := make(chan sample)
	var wg sync.WaitGroup
	for n := 0; n < *parallel; n++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for item := range jobs {
				start := time.Now()
				protocol := item.Protocol
				if protocol == "" {
					protocol = "chat"
				}
				request, e := ag.NormalizeProtocolRequest(protocol, item.Body)
				id := fmt.Sprintf("semantic-%d-%s-%s", start.UnixNano(), item.ID, item.Lang)
				events := []ag.UsageEvent{}
				c := &ag.SemanticClassifier{Endpoint: *endpoint, Model: *primary, ReviewerModel: *reviewer, Token: strings.TrimSpace(string(token)), Client: &http.Client{Timeout: 60 * time.Second, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}, OnUsage: func(u ag.UsageEvent) error { events = append(events, u); return nil }}
				guardDecision := "not_run_isolated"
				var result ag.Classification
				if e == nil {
					meta := ag.PipelineMeta{RequestID: id, Region: *region, APIKeyID: *keyID, ClientHeaders: http.Header{"User-Agent": {"ai-gateway-semantic-eval/1"}}}
					result, guardDecision, e = classifySample(context.Background(), request, *guard, c, meta)
				}
				record := map[string]any{"request_id": id, "at": start.UTC(), "case_id": item.ID, "language": item.Lang, "source": item.Source, "split": item.Split, "expected_task": item.Expected, "reviewer_complexity": item.Complexity, "primary": *primary, "reviewer": *reviewer, "guard": guardDecision, "classification": result, "classification_calls": events, "latency_ms": time.Since(start).Milliseconds(), "business_upstream_called": false, "ok": e == nil}
				record["protocol"] = protocol
				if e != nil {
					record["error"] = "classification_or_preflight_failed"
				}
				mu.Lock()
				if encoder.Encode(record) != nil || file.Sync() != nil {
					fatal("evidence_write_failed")
				}
				fmt.Printf("case=%s language=%s ok=%t latency_ms=%d\n", item.ID, item.Lang, e == nil, time.Since(start).Milliseconds())
				mu.Unlock()
			}
		}()
	}
	count := 0
outer:
	for _, item := range f.Cases {
		if *split != "" && item.Split != *split {
			continue
		}
		for _, lang := range []string{"zh", "en", "mixed"} {
			if *limit > 0 && count >= *limit {
				break outer
			}
			body, ok := item.Variants[lang]
			if !ok {
				fatal("language variant missing")
			}
			jobs <- sample{item.ID, lang, item.Source, item.Split, item.Expected, item.Complexity, item.Protocol, body}
			count++
		}
	}
	close(jobs)
	wg.Wait()
	fmt.Printf("completed=%d business_calls=0\n", count)
}

func classifySample(ctx context.Context, request ag.Request, guardURL string, classifier ag.TaskClassifier, meta ag.PipelineMeta) (ag.Classification, string, error) {
	decision := "not_run_isolated"
	if guardURL != "" {
		check := ag.HTTPPreflightChecker{Endpoint: guardURL}
		verdict, err := check.EvaluateWithMeta(ctx, request, meta)
		decision = string(verdict.Decision)
		if err != nil || verdict.Decision != ag.PreflightAllow {
			return ag.Classification{}, decision, fmt.Errorf("guard_not_allowed")
		}
		if verdict.SanitizedRequest == nil {
			return ag.Classification{}, "unavailable", fmt.Errorf("guard_prepared_input_missing")
		}
		request = *verdict.SanitizedRequest
	}
	result, err := classifier.Classify(ctx, request, meta)
	return result, decision, err
}
func fatal(s string) { fmt.Fprintln(os.Stderr, s); os.Exit(1) }
