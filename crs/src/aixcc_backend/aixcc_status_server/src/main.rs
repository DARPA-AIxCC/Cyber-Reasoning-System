use axum::extract::{self, State};
use axum::response::IntoResponse;
use axum::routing::get;
use axum::routing::post;
use axum::Extension;
use axum::{http::StatusCode, Json, Router};
use clap::Parser;
use log::info;
use serde::Deserialize;
use serde_json::json;
use std::collections::HashMap;
use std::env;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};
use std::thread::available_parallelism;
use tokio::net::TcpListener;
use tracing_subscriber::filter::LevelFilter;
use tracing_subscriber::EnvFilter;
pub type Result<T> = core::result::Result<T, Error>;
pub type Error = Box<dyn std::error::Error>;

#[derive(Deserialize)]
struct ReturnSubject {
    subject: String,
    bug_id: String,
    id: usize,
    subject_name: String,
}

#[derive(Parser, Debug)]
#[clap(version, about)]
struct Arguments {
    #[clap(env = "AIXCC_CP_ROOT")]
    directory: PathBuf,

    /// Provide destination directory where to write different configurations
    #[clap(env = "AIXCC_CRS_SCRATCH_SPACE")]
    destination_directory: PathBuf,
}

#[derive(Clone)]
struct AppState {
    // Available projects
    pub projects: Vec<Project>,
    pub machines: usize,
    pub cpus_per_machine: usize,
}

#[derive(Clone, PartialEq, Eq, Hash)]
struct Project {
    pub project_id: usize,

    pub cs_name: String,

    pub harness_id: String,
    pub subject_name: String,
}

#[derive(Deserialize)]
struct AcquireSubject {
    pub id: String,
}

#[derive(Clone)]
struct Projects {
    projects: Arc<Mutex<Vec<Project>>>,
    distributions: Arc<Mutex<HashMap<String, Vec<Project>>>>,
}

impl Projects {
    fn add(&self, project: Project) {
        self.projects.lock().unwrap().push(project)
    }

    fn get(&self) -> Option<Project> {
        self.projects.lock().unwrap().pop()
    }

    fn is_empty(&self) -> bool {
        self.projects.lock().unwrap().is_empty()
    }
}

async fn subject_count(State(state): State<AppState>) -> impl IntoResponse {
    (
        StatusCode::OK,
        Json(json!({
            "count": state.projects.len()
        })),
    )
}

async fn get_health(State(_state): State<AppState>) -> impl IntoResponse {
    info!("Health request");

    (
        StatusCode::OK,
        Json(json!({
            "status": "healthy"
        })),
    )
}

async fn has_subject(
    Extension(projects): Extension<Projects>,
    State(_state): State<AppState>,
) -> impl IntoResponse {
    if projects.is_empty() {
        (
            StatusCode::NOT_FOUND,
            Json(json!({
                "status": "YES"
            })),
        )
    } else {
        (
            StatusCode::OK,
            Json(json!({
                "status": "YES",
            })),
        )
    }
}

async fn get_next_subject(
    Extension(projects): Extension<Projects>,
    State(state): State<AppState>,
    extract::Json(AcquireSubject { id: caller_id }): extract::Json<AcquireSubject>,
) -> impl IntoResponse {
    info!("Get next subject");

    let total_count = state.projects.len();

    if total_count < state.machines {
        let mut dist = projects.distributions.lock().unwrap();

        if !dist.contains_key(&caller_id) {
            dist.insert(caller_id.clone(), vec![]);
        }

        for project in projects.projects.lock().unwrap().iter() {
            if dist.get(&caller_id).unwrap().contains(project) {
                continue;
            }

            dist.get_mut(&caller_id).unwrap().push(project.clone());

            return (
                StatusCode::OK,
                Json(json!({
                    "subject": project.cs_name.as_str(),
                    "bug_id": project.harness_id,
                    "cpus":  (state.cpus_per_machine / total_count - 2).clamp(6, 50),
                    "subject_name": project.subject_name,
                })),
            );
        }
        return (
            StatusCode::NOT_FOUND,
            Json(json!({
                "status": "not found"
            })),
        );
    }

    let bound = total_count / state.machines;
    let residue = total_count % state.machines;

    match projects.get() {
        None => (
            StatusCode::NOT_FOUND,
            Json(json!({
                "status": "not found"
            })),
        ),
        Some(project) => {
            let tasks_on_machine = if project.project_id % state.machines < residue {
                bound + 1
            } else {
                bound
            };
            let cpu_count = (state.cpus_per_machine / tasks_on_machine - 1).clamp(4, 50);

            info!(
                "Getting subject: {} - {} - {}",
                project.project_id, project.cs_name, project.harness_id
            );
            (
                StatusCode::OK,
                Json(json!({
                    "subject": project.cs_name.as_str(),
                    "bug_id": project.harness_id,
                    "cpus": cpu_count,
                    "subject_name": project.subject_name,
                })),
            )
        }
    }
}

async fn return_subject(
    Extension(projects): Extension<Projects>,
    State(_state): State<AppState>,
    extract::Json(ReturnSubject {
        subject,
        bug_id,
        id,
        subject_name,
    }): extract::Json<ReturnSubject>,
) -> impl IntoResponse {
    info!("Returning subject: {} - {}", subject, bug_id);

    projects.add(Project {
        project_id: id,
        cs_name: subject,
        harness_id: bug_id,
        subject_name,
    });

    (
        StatusCode::OK,
        Json(json!({
            "status": "ok"
        })),
    )
}

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

    let args = Arguments::parse();

    // Let server listen on part 80
    let listener = TcpListener::bind("0.0.0.0:9042").await.unwrap();
    info!("{:<12} - {:?}\n", "LISTENING", listener.local_addr());

    let state = create_app_state(&args)?;

    let routes = Router::new()
        .route("/health/", get(get_health))
        .route("/has_subject/", get(has_subject))
        .route("/next_subject/", post(get_next_subject))
        .route("/return_subject/", post(return_subject))
        .route("/subject_count/", get(subject_count))
        .with_state(state.clone())
        .layer(Extension(Projects {
            projects: Arc::new(Mutex::new(state.projects.clone())),
            distributions: Arc::new(Mutex::new(HashMap::new())),
        }));

    Ok(axum::serve(listener, routes.into_make_service()).await?)
}

fn create_app_state(args: &Arguments) -> Result<AppState> {
    let project_descriptions = metadata_extraction::fs::get_challenges(&args.directory);

    let projects = project_descriptions
        .iter()
        .flat_map(|(_, metadata)| {
            metadata
                .harnesses
                .iter()
                .enumerate()
                .map(|(id, harness)| {
                    let y = id + 1;
                    let harness_identifier = &harness.0 .0;
                    (
                        metadata_extraction::fs::sanitise_directory_name(metadata.cp_name.as_str()),
                        y.to_string(),
                        format!("{harness_identifier}_{y}"),
                    )
                })
                .collect::<Vec<_>>()
        })
        .enumerate()
        .map(
            |(project_id, (cs_name, harness_id, subject_name))| Project {
                project_id,
                cs_name,
                harness_id,
                subject_name,
            },
        )
        .collect::<Vec<_>>();
    if projects.is_empty() {
        return Err("No projects found".into());
    }

    let machines = env::var("AIXCC_CP_MACHINES")
        .unwrap_or_else(|_| "1".to_string())
        .parse::<usize>()
        .unwrap();

    let cpus_per_machine = available_parallelism().unwrap().get();

    Ok(AppState {
        projects,
        machines,
        cpus_per_machine,
    })
}
