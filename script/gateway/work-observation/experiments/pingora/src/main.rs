//! Synthetic-only transport experiment. No employee data and no body persistence.
use async_trait::async_trait;
use bytes::Bytes;
use pingora_core::{server::Server, upstreams::peer::HttpPeer, Result};
use pingora_proxy::{ProxyHttp, Session};
use sha2::{Digest, Sha256};
use std::{sync::{Arc, atomic::{AtomicU64, AtomicUsize, Ordering}, mpsc::{sync_channel, SyncSender}}, time::Duration};

#[derive(Default)]
struct Stats {
    bytes: AtomicU64,
    chunks: AtomicU64,
    drops: AtomicU64,
    queued: AtomicUsize,
    requests: AtomicU64,
}
struct Proxy {
    upstream: String,
    tap: Option<SyncSender<Bytes>>,
    stats: Arc<Stats>,
}
impl Proxy {
    fn observe(&self, body: &Option<Bytes>) {
        let Some(tx) = &self.tap else { return };
        let Some(body) = body else { return };
        let n = body.len();
        if self.stats.queued.fetch_update(Ordering::Relaxed, Ordering::Relaxed,
            |old| old.checked_add(n).filter(|&new| new <= 64 * 1024 * 1024)).is_err() {
            self.stats.drops.fetch_add(1, Ordering::Relaxed);
            return;
        }
        if tx.try_send(body.clone()).is_err() {
            self.stats.queued.fetch_sub(n, Ordering::Relaxed);
            self.stats.drops.fetch_add(1, Ordering::Relaxed);
        }
    }
}
#[async_trait]
impl ProxyHttp for Proxy {
    type CTX = ();
    fn new_ctx(&self) {}
    async fn upstream_peer(&self, _: &mut Session, _: &mut ()) -> Result<Box<HttpPeer>> {
        let mut peer = HttpPeer::new(self.upstream.as_str(), false, String::new());
        peer.options.connection_timeout = Some(Duration::from_secs(5));
        peer.options.read_timeout = Some(Duration::from_secs(60));
        peer.options.write_timeout = Some(Duration::from_secs(60));
        Ok(Box::new(peer))
    }
    async fn request_body_filter(&self, _: &mut Session, body: &mut Option<Bytes>, _: bool, _: &mut ()) -> Result<()> {
        self.observe(body);
        Ok(())
    }
    fn upstream_response_body_filter(&self, _: &mut Session, body: &mut Option<Bytes>, _: bool, _: &mut ()) -> Result<Option<Duration>> {
        self.observe(body);
        Ok(None)
    }
    async fn logging(&self, _: &mut Session, _: Option<&pingora_core::Error>, _: &mut ()) {
        self.stats.requests.fetch_add(1, Ordering::Relaxed);
    }
    fn request_summary(&self, _: &Session, _: &()) -> String { "synthetic-benchmark".into() }
}
fn main() {
    let addr = std::env::var("BENCH_LISTEN").unwrap_or_else(|_| "127.0.0.1:18083".into());
    assert!(addr.starts_with("127.0.0.1:"), "experiment is loopback-only");
    let upstream = std::env::var("BENCH_UPSTREAM").unwrap_or_else(|_| "127.0.0.1:18080".into());
    assert!(upstream.starts_with("127.0.0.1:"), "synthetic upstream only");
    let stats = Arc::new(Stats::default());
    let tap = if std::env::var("BENCH_CAPTURE").as_deref() == Ok("1") {
        let (tx, rx) = sync_channel::<Bytes>(4096);
        let stats = stats.clone();
        std::thread::spawn(move || {
            while let Ok(bytes) = rx.recv() {
                std::hint::black_box(Sha256::digest(&bytes));
                stats.bytes.fetch_add(bytes.len() as u64, Ordering::Relaxed);
                stats.chunks.fetch_add(1, Ordering::Relaxed);
                stats.queued.fetch_sub(bytes.len(), Ordering::Relaxed);
            }
        });
        Some(tx)
    } else { None };
    let report = stats.clone();
    std::thread::spawn(move || loop {
        std::thread::sleep(Duration::from_secs(2));
        eprintln!("{}", serde_json::json!({"bytes":report.bytes.load(Ordering::Relaxed),
            "chunks":report.chunks.load(Ordering::Relaxed),"drops":report.drops.load(Ordering::Relaxed),
            "queued":report.queued.load(Ordering::Relaxed),"requests":report.requests.load(Ordering::Relaxed)}));
    });
    let mut server = Server::new(None).unwrap();
    let conf = Arc::get_mut(&mut server.configuration).unwrap();
    conf.threads = 2;
    // In 0.9.0 this counts total attempts, including the initial connection.
    // One attempt means no replay; zero silently skips the upstream loop.
    conf.max_retries = 1;
    conf.upstream_keepalive_pool_size = 128;
    server.bootstrap();
    let mut service = pingora_proxy::http_proxy_service(&server.configuration, Proxy { upstream, tap, stats });
    service.add_tcp(&addr);
    server.add_service(service);
    server.run_forever();
}
