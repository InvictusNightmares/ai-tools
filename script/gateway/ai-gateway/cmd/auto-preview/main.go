package main

import (
	"log"
	"net/http"
	"os"

	autogateway "local/ai-gateway/auto"
)

func main() {
	address := os.Getenv("AUTO_GATEWAY_LISTEN")
	if address == "" {
		address = "127.0.0.1:8091"
	}
	handler := &autogateway.HTTPServer{Gateway: autogateway.NewAutoGateway()}
	server := &http.Server{Addr: address, Handler: handler}
	log.Printf("auto gateway route preview listening on %s", address)
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatal(err)
	}
}
