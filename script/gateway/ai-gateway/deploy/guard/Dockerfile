FROM golang:1.27.1-bookworm AS build
WORKDIR /src
COPY . .
RUN CGO_ENABLED=0 go build -o /out/preflight-api ./cmd/preflight-api

FROM ubuntu:resolute-20260108
RUN useradd --system --uid 10001 --create-home gateway
COPY --from=build /out/preflight-api /preflight-api
USER gateway
ENTRYPOINT ["/preflight-api"]
