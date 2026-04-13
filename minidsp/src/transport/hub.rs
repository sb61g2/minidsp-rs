//! Provides a way to share a transport on a frame level, all received frames are forward to all clients.

use std::{
    pin::Pin,
    sync::{Arc, Mutex, RwLock},
    task::{Context, Poll},
};

use bytes::Bytes;
use futures::{channel::mpsc, stream::SplitSink, Sink, SinkExt, Stream, StreamExt};
use futures_util::ready;
use pin_project::pin_project;
use tokio::sync::broadcast;
use tokio_stream::wrappers::BroadcastStream;

use super::{MiniDSPError, Transport};
use crate::utils::OwnedJoinHandle;

const CAPACITY: usize = 100;

/// Clonable transport which implements frame level forwarding
#[pin_project]
pub struct Hub {
    // Shared data between clients
    inner: Arc<Mutex<Option<Inner>>>,
    handles: Arc<Mutex<Vec<OwnedJoinHandle<()>>>>,

    /// Stream where client can read frames from the device.
    #[pin]
    device_rx: BroadcastStream<Bytes>,
    /// Sink where client can write frames to the device.
    #[pin]
    device_tx: mpsc::Sender<Bytes>,
}

impl Hub {
    pub fn new(transport: Transport) -> Self {
        let (read_tx, read_rx) = broadcast::channel::<Bytes>(CAPACITY);
        let (send_tx, mut send_rx) = mpsc::channel(CAPACITY);
        let (device_tx, mut device_rx) = transport.split();

        // Create the Arc before spawning tasks so the read task can signal death by taking Inner.
        let inner_arc = Arc::new(Mutex::new(Some(Inner::new(read_tx, device_tx))));

        let read_handle = {
            let read_tx_shared = inner_arc.lock().unwrap().as_ref().unwrap().device_rx.clone();
            let inner_for_death = inner_arc.clone();
            OwnedJoinHandle::new(tokio::spawn(async move {
                while let Some(frame) = device_rx.next().await {
                    match frame {
                        Ok(frame) => {
                            let result = {
                                let read_tx = read_tx_shared.write().unwrap();
                                read_tx.send(frame)
                            };
                            if let Err(e) = result {
                                log::error!("send error {e}");
                                break;
                            }
                        }
                        Err(e) => {
                            log::error!("recv error {e}");
                            break;
                        }
                    }
                }
                // Signal connection death to all Hub consumers.
                //
                // When the TCP read side closes (EOF or BrokenPipe), this read task exits the
                // while loop above. At that point nothing automatically drops the
                // broadcast::Sender, so every BroadcastStream subscriber (including
                // task_inner's `while let Some(frame) = transportlocal.next().await` loop in
                // device_manager.rs) would block forever waiting for a sender that will never
                // produce another value — causing the daemon to hang until HAOS kills it.
                //
                // Dropping `read_tx_shared` first brings the Arc<RwLock<Sender>> refcount from
                // 2 (Inner + this task) down to 1.  Taking Inner from the shared Arc then
                // brings it to 0, which drops the broadcast::Sender.  The broadcast runtime
                // wakes all waiting receivers with RecvError::Closed, so every BroadcastStream
                // returns None, the device_manager loop exits cleanly, and the 1-second
                // reconnect delay fires as intended.
                drop(read_tx_shared);
                inner_for_death.lock().unwrap().take();
            }))
        };

        let send_handle = {
            let transport_sink_shared =
                inner_arc.lock().unwrap().as_ref().unwrap().transport_sink.clone();

            OwnedJoinHandle::new(tokio::spawn({
                async move {
                    let mut transport_sink = transport_sink_shared.lock().await;
                    while let Some(frame) = send_rx.next().await {
                        let res = transport_sink.send(frame).await;
                        if let Err(e) = res {
                            log::error!("error sending to device: {e}");
                            break;
                        }
                    }
                }
            }))
        };

        let handles = Arc::new(Mutex::new(vec![read_handle, send_handle]));

        Self {
            inner: inner_arc,
            handles,
            device_rx: BroadcastStream::new(read_rx),
            device_tx: send_tx,
        }
    }

    pub async fn shutdown(&self) {
        let handles: Vec<_> = { self.handles.lock().unwrap().drain(..).collect() };
        for h in handles.iter() {
            h.abort();
        }
        let inner = { self.inner.lock().unwrap().take() };
        if let Some(inner) = inner {
            // Drop the transport sink rather than calling close(). If the
            // underlying connection already errored, the SinkMapErr wrapper
            // will have consumed its closure and calling close() (which
            // internally calls poll_close → map_err) would panic with
            // "polled MapErr after completion".
            drop(inner.transport_sink.lock().await);
        }
        for h in handles {
            let res = h.await;
            if let Err(e) = res {
                if !e.is_cancelled() {
                    log::error!("error joining handle: {e}");
                }
            }
        }
    }

    /// Clones the transport if it is still available, returns None if it has been closed
    pub fn try_clone(&self) -> Option<Self> {
        let inner = self.inner.lock().unwrap();
        let device_rx = BroadcastStream::new(inner.as_ref()?.device_rx.read().unwrap().subscribe());
        Some(Self {
            inner: self.inner.clone(),
            handles: self.handles.clone(),
            device_rx,
            device_tx: self.device_tx.clone(),
        })
    }
}

impl Stream for Hub {
    type Item = Result<Bytes, MiniDSPError>;

    fn poll_next(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Option<Self::Item>> {
        let mut device_rx: Pin<&mut BroadcastStream<_>> = self.project().device_rx;
        loop {
            let res = ready!(device_rx.as_mut().poll_next(cx));
            return Poll::Ready(match res {
                Some(Ok(obj)) => Some(Ok(obj)),
                Some(Err(e)) => {
                    log::warn!("lost messages: {e:?}");
                    continue;
                }
                None => None,
            });
        }
    }
}

impl Sink<Bytes> for Hub {
    type Error = MiniDSPError;

    fn poll_ready(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Result<(), Self::Error>> {
        self.project()
            .device_tx
            .poll_ready(cx)
            .map_err(|_| MiniDSPError::TransportClosed)
    }

    fn start_send(self: Pin<&mut Self>, item: Bytes) -> Result<(), Self::Error> {
        self.project()
            .device_tx
            .start_send(item)
            .map_err(|_| MiniDSPError::TransportClosed)
    }

    fn poll_flush(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Result<(), Self::Error>> {
        self.project()
            .device_tx
            .poll_flush(cx)
            .map_err(|_| MiniDSPError::TransportClosed)
    }

    fn poll_close(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Result<(), Self::Error>> {
        self.project()
            .device_tx
            .poll_close(cx)
            .map_err(|_| MiniDSPError::TransportClosed)
    }
}

struct Inner {
    // Broadcast sender used for creating receivers through .subscribe()
    device_rx: Arc<RwLock<broadcast::Sender<Bytes>>>,
    transport_sink: Arc<tokio::sync::Mutex<SplitSink<Transport, Bytes>>>,
}

impl Inner {
    pub fn new(
        device_rx: broadcast::Sender<Bytes>,
        transport_sink: SplitSink<Transport, Bytes>,
    ) -> Self {
        Self {
            device_rx: Arc::new(RwLock::new(device_rx)),
            transport_sink: Arc::new(tokio::sync::Mutex::new(transport_sink)),
        }
    }
}
