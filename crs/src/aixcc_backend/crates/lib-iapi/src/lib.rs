use crate::client::Error;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

pub mod client;

#[derive(Serialize, Deserialize, Debug, PartialEq)]
pub struct IAPIServerResponse {
    pub status: Status,
    pub vd_uuid: Option<String>,
    pub cpv_uuid: Option<String>,
    pub gp_uuid: Option<String>,
}

#[derive(Serialize, Deserialize, Debug, PartialEq)]
pub enum Status {
    /// Health status
    #[serde(rename = "ok")]
    Ok,

    /// Accept query
    #[serde(rename = "accepted")]
    Accepted,

    /// Reject query
    #[serde(rename = "rejected")]
    Rejected,

    /// Pending query
    #[serde(rename = "pending")]
    Pending,

    /// Respond with unexpected error
    UnexpectedError(String),
}

#[derive(Serialize, Deserialize, Debug, PartialEq)]
pub enum VDSStatus {
    #[serde(rename = "accepted")]
    Accepted,
    #[serde(rename = "pending")]
    Pending,
    #[serde(rename = "rejected")]
    Rejected,
}

impl TryFrom<String> for VDSStatus {
    type Error = Error;

    fn try_from(value: String) -> Result<Self, Self::Error> {
        match value.as_str() {
            "accepted" => Ok(VDSStatus::Accepted),
            "pending" => Ok(VDSStatus::Pending),
            "rejected" => Ok(VDSStatus::Rejected),
            _ => {
                println!("INDDEED INVALID {value}");
                Err("Invalid".into())
            }
        }
    }
}

pub fn status_accepted() -> IAPIServerResponse {
    IAPIServerResponse {
        status: Status::Accepted,
        vd_uuid: None,
        cpv_uuid: None,
        gp_uuid: None,
    }
}

pub fn status_accepted_vd(uuid: Uuid) -> IAPIServerResponse {
    IAPIServerResponse {
        status: Status::Accepted,
        vd_uuid: Some(uuid.to_string()),
        cpv_uuid: None,
        gp_uuid: None,
    }
}

pub fn status_accepted_cpv(uuid: Uuid) -> IAPIServerResponse {
    IAPIServerResponse {
        status: Status::Accepted,
        vd_uuid: None,
        cpv_uuid: Some(uuid.to_string()),
        gp_uuid: None,
    }
}

pub fn status_pending_cpv(uuid: Uuid) -> IAPIServerResponse {
    IAPIServerResponse {
        status: Status::Pending,
        vd_uuid: None,
        cpv_uuid: Some(uuid.to_string()),
        gp_uuid: None,
    }
}

pub fn status_rejected_cpv(uuid: Uuid) -> IAPIServerResponse {
    IAPIServerResponse {
        status: Status::Rejected,
        vd_uuid: None,
        cpv_uuid: Some(uuid.to_string()),
        gp_uuid: None,
    }
}

pub fn status_rejected() -> IAPIServerResponse {
    IAPIServerResponse {
        status: Status::Rejected,
        vd_uuid: None,
        cpv_uuid: None,
        gp_uuid: None,
    }
}

pub fn status_unknown(message: &str) -> IAPIServerResponse {
    IAPIServerResponse {
        status: Status::UnexpectedError(message.to_string()),
        vd_uuid: None,
        cpv_uuid: None,
        gp_uuid: None,
    }
}

pub fn status_health_ok() -> IAPIServerResponse {
    IAPIServerResponse {
        status: Status::Ok,
        vd_uuid: None,
        cpv_uuid: None,
        gp_uuid: None,
    }
}

pub fn status_accepted_gp(uuid: Uuid) -> IAPIServerResponse {
    status_gp(uuid, Status::Accepted)
}

pub fn status_gp(uuid: Uuid, status: Status) -> IAPIServerResponse {
    IAPIServerResponse {
        status,
        vd_uuid: None,
        cpv_uuid: None,
        gp_uuid: Some(uuid.to_string()),
    }
}

#[derive(Deserialize, Serialize, Debug, Hash, PartialEq, Eq, Clone)]
pub struct ProofOfVulnerabilityDiscovery {
    pub cp_name: String,
    pub pou: ProofOfUnderstanding,
    pub pov: ProofOfVulnerability,
}

#[derive(Deserialize, Serialize, Debug, Hash, PartialEq, Eq, Clone)]
pub struct ProofOfUnderstanding {
    pub commit_sha1: String,
    pub sanitizer: String,
}

/// Proof of Validation
#[derive(Deserialize, Serialize, Debug, Hash, PartialEq, Eq, Clone)]
pub struct ProofOfVulnerability {
    pub harness: String,
    pub data: String, // Base64-encoded string
}

/// Generated Patch Validation
#[derive(Serialize, Deserialize, Debug)]
pub struct GeneratePatchCheckRequest {
    pub cpv_uuid: String,
    pub data: String,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn response_status() {
        assert_eq!(status_accepted().status, Status::Accepted);

        assert_eq!(status_rejected().status, Status::Rejected);
        assert_eq!(
            status_unknown("Foo").status,
            Status::UnexpectedError("Foo".into())
        );
        assert_eq!(status_health_ok().status, Status::Ok);
    }
}
