use clap::Parser;
use std::env;
use tokio::net::TcpListener;
use tracing::info;
use tracing::level_filters::LevelFilter;
use tracing_subscriber::EnvFilter;
use url::Url;

mod config;
mod router;
mod state;
mod validating_router;

pub type Result<T> = core::result::Result<T, Error>;
pub type Error = Box<dyn std::error::Error>;

#[tokio::main]
async fn main() -> Result<()> {
    // Set logging to INFO
    tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::builder()
                .with_default_directive(LevelFilter::INFO.into())
                .from_env_lossy(),
        )
        .init();

    let binding = env::var_os("AIXCC_API_HOSTNAME");

    let address = binding
        .as_ref()
        .and_then(|os| os.to_str())
        .ok_or("Invalid address in AIXCC_API_HOSTNAME")?;

    let address = Url::parse(address)?;

    let args = config::Arguments::parse();

    let listener = TcpListener::bind("0.0.0.0:8080").await.unwrap();
    info!("{:<12} - {:?}\n", "LISTENING", listener.local_addr());

    let state = state::create_app_state(&args, address)?;
    let routes = router::create_app(state);

    axum::serve(listener, routes.into_make_service())
        .await
        .unwrap();

    Ok(())
}
