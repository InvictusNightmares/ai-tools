#!/bin/sh
# Run only in /data/work-observation-lab on the GPU host, after copying experiments.
set -eu
test "$(pwd)" = /data/work-observation-lab
docker build --network=host --memory=2g --build-arg DEBIAN_MIRROR=mirrors.tuna.tsinghua.edu.cn \
  -f Dockerfile.rust-build -t work-observation-rust-build:20260917 .
docker run --rm --name work-observation-go-build --cpus=2 --memory=2g --memory-swap=2g \
  -e CGO_ENABLED=0 -e GOCACHE=/cache -v "$PWD/go-cache:/cache" \
  -v "$PWD:/work" -w /work golang:1.27.1-bookworm sh -c \
  'gofmt -w go-proxy/main.go bench/main.go && go build -trimpath -o go-proxy-bin go-proxy/main.go && go build -trimpath -o bench-bin bench/main.go'
docker run --rm --name work-observation-rust-build --cpus=2 --memory=3g --memory-swap=3g \
  -e CARGO_BUILD_JOBS=2 -v "$PWD:/work" \
  -v "$PWD/cargo-cache:/usr/local/cargo/registry" -w /work/pingora work-observation-rust-build:20260917 \
  sh -c 'rustc --version && cargo build --release --locked'
