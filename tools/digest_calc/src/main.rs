// This program calculates the SEV-SNP launch digest, which is used for 
// verifying the integrity of a virtual machine at launch. It computes 
// cryptographic hashes of the kernel, initrd, cmdline, and OVMF files, 
// and generates the corresponding launch digest required for secure attestation 
// in SEV-SNP environments.

use bincode;
use clap::Parser;
use serde::{Deserialize, Serialize};
use sev::error::MeasurementError;
use sev::firmware::guest::{GuestPolicy, PlatformInfo};
use sev::firmware::host::TcbVersion;
use sev::measurement::sev_hashes::SevHashes;
use sev::measurement::snp::{
    calc_snp_ovmf_hash, snp_calc_launch_digest, SnpLaunchDigest, SnpMeasurementArgs,
};
use sev::measurement::vcpu_types::CpuType;
use sev::measurement::vmsa::{ GuestFeatures, VMMType};
use std::convert::Into;
use std::fmt::Display;
use std::fs;


use std::path::PathBuf;
use hex_buffer_serde::{Hex as _, HexForm};

///Length fo the FamilyID and the ImageID data types in bytes
pub const IDBLOCK_ID_BYTES :usize = 16;

#[derive(Copy, Clone, Debug, PartialEq, Serialize, Deserialize, Default)]
///Describes the CPU generation
pub enum ProductName {
    #[default]
    Milan,
    Genoa,
}

impl Display for ProductName {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let s = match self {
            ProductName::Milan => "Milan",
            ProductName::Genoa => "Genoa",
        };
        write!(f, "{}", s)
    }
}


/// Converts a byte slice to a hexadecimal string representation.
fn bytes_to_hex(bytes: &[u8]) -> String {
    bytes.iter().map(|byte| format!("{:02x}", byte)).collect()
}

/// Calculates the launch measurement digest using the SEV-SNP arguments.
fn calculate_launch_measurment(
    snp_measure_args: SnpMeasurementArgs,
) -> Result<[u8; 384 / 8], String> {
    // Calculate the launch digest
    let ld = snp_calc_launch_digest(snp_measure_args)
        .map_err(|e| format!("Failed to compute launch digest: {:?}", e))?;

    // Serialize the launch digest
    let ld_vec = bincode::serialize(&ld).map_err(|e| {
        format!(
            "Failed to bincode serialize SnpLaunchDigest to Vec<u8>: {:?}",
            e
        )
    })?;

    // Convert the serialized data into a fixed-length byte array
    let ld_arr: [u8; 384 / 8] = ld_vec
        .try_into()
        .map_err(|_| "SnpLaunchDigest has unexpected length".to_string())?;

    Ok(ld_arr)
}

/// Calculates the OVMF file hash.
pub fn get_ovmf_hash_from_file(ovmf_file: PathBuf) -> Result<SnpLaunchDigest, MeasurementError> {
    calc_snp_ovmf_hash(ovmf_file)
}

/// Retrieves the hashes for kernel, initrd, and cmdline files.
pub fn get_hashes_from_files(
    kernel_file: PathBuf,
    initrd_file: PathBuf,
    append: Option<&str>,
) -> Result<SevHashes, MeasurementError> {
    SevHashes::new(kernel_file, Some(initrd_file), append)
}

#[derive(Parser, Debug)]
#[command(
    version,
    about,
)]
struct Args {
    ///Path to the vm config toml file. This is require to compute the expected attestation value for the VM
    #[arg(long)]
    vm_definition: String,
}


#[derive(Serialize, Deserialize, Default, Debug)]
///User facing config struct to specify a VM.
///Used to compute the epxected launch measurment
pub struct VMDescription {
    pub host_cpu_family: ProductName,
    pub vcpu_count: u32,
    pub ovmf_file: String,
    /// Security relevant SEV configuration/kernel features. Defined in the VMSA of the VM. Thus they affect the computation of the expected launch measurement. See `SEV_FEATURES` in Table B-4 in https://www.amd.com/content/dam/amd/en/documents/processor-tech-docs/programmer-references/24593.pdf
    ///TODO: implement nice way to detect which features are used on a given system
    pub guest_features: u64,
    pub kernel_file: String,
    pub initrd_file: String,
    pub kernel_cmdline: String,
    pub platform_info: PlatformInfo,
    ///Mininum required committed version numbers
    ///Committed means that the platform cannot be rolled back to a prior
    ///version
    pub min_commited_tcb: TcbVersion,
    /// Policy passed to QEMU and reflected in the attestation report
    pub guest_policy: GuestPolicy,
    #[serde(with = "HexForm")]
    pub family_id: [u8; IDBLOCK_ID_BYTES],
    #[serde(with = "HexForm")]
    pub image_id: [u8; IDBLOCK_ID_BYTES],
}


fn main() {

    #[allow(dead_code)]
    #[derive(Debug, Serialize)]
    struct Output {
        kernel_hash: String,
        initrd_hash: String,
        cmdline_hash: String,
        ovmf_hash: String,
        vcpus: u32,
        vcputype: u32,
        vmmtype: u32,
        guest_features: String,
        expected_hash: String,
    }

    let args = Args::parse();

    let vm_description: VMDescription = toml::from_str(&fs::read_to_string(&args.vm_definition).unwrap()).unwrap();

    let vcpus: u32 = vm_description.vcpu_count;

    let vcpu_type_str = "EpycV4";
    let vcpu_type = match vcpu_type_str {
        "Epyc" => CpuType::Epyc,
        "EpycV1" => CpuType::EpycV1,
        "EpycV2" => CpuType::EpycV2,
        "EpycIBPB" => CpuType::EpycIBPB,
        "EpycV3" => CpuType::EpycV3,
        "EpycV4" => CpuType::EpycV4,
        "EpycRome" => CpuType::EpycRome,
        "EpycRomeV1" => CpuType::EpycRomeV1,
        "EpycRomeV2" => CpuType::EpycRomeV2,
        "EpycRomeV3" => CpuType::EpycRomeV3,
        "EpycMilan" => CpuType::EpycMilan,
        "EpycMilanV1" => CpuType::EpycMilanV1,
        "EpycMilanV2" => CpuType::EpycMilanV2,
        "EpycGenoa" => CpuType::EpycGenoa,
        "EpycGenoaV1" => CpuType::EpycGenoaV1,
        _ => CpuType::EpycV4, // Default to EpycV4
    };

    let vmm_type_str = "QEMU";
    let vmm_type = match vmm_type_str {
        "QEMU" => Some(VMMType::QEMU),
        "EC2" => Some(VMMType::EC2),
        "KRUN" => Some(VMMType::KRUN),
        _ => Some(VMMType::QEMU),
    };


    let guest_features_string  = format!("0x{:X}", vm_description.guest_features);
    let guest_features: u64 =
    u64::from_str_radix(&guest_features_string[2..], 16).unwrap();

    let omvf_file: PathBuf = vm_description.ovmf_file.clone().into();
    // Step 1: Get the hash of the OVMF file
    let ovmf_hash = get_ovmf_hash_from_file(omvf_file.clone()).unwrap();
    let ovmf_bytes: Vec<u8> = bincode::serialize(&ovmf_hash).unwrap();
    let ovmf_binding = ovmf_hash.get_hex_ld();
    
    // Step 2: Get the hash of the kernel, initrd, and cmdline
    let SevHashes {
        kernel_hash,
        initrd_hash,
        cmdline_hash,
    } = get_hashes_from_files(
        vm_description.kernel_file.clone().into(),
        vm_description.initrd_file.clone().into(),
        Some(&vm_description.kernel_cmdline),
    )
    .unwrap();

    // Step 3: Calculate the launch digest
    let arguments = SnpMeasurementArgs {
        ovmf_file: Some(omvf_file),
        kernel_file: None,
        initrd_file: None,
        append: None,

        vcpus,
        vcpu_type,
        vmm_type,
        guest_features: GuestFeatures(guest_features),

        ovmf_hash_str: Some(ovmf_binding.as_str()),
        kernel_hash: Some(kernel_hash),
        initrd_hash: Some(initrd_hash),
        append_hash: Some(cmdline_hash),
    };

    let expected_hash = calculate_launch_measurment(arguments).unwrap();


    let output = Output {
        kernel_hash: bytes_to_hex(&kernel_hash),
        initrd_hash: bytes_to_hex(&initrd_hash),
        cmdline_hash: bytes_to_hex(&cmdline_hash),
        ovmf_hash: bytes_to_hex(&ovmf_bytes),
        vcpus,
        vcputype: vcpu_type as u32,
        vmmtype: vmm_type.unwrap() as u32,
        guest_features: guest_features_string,
        expected_hash:  bytes_to_hex(&expected_hash)
    };

    println!("{}", serde_json::to_string_pretty(&output).unwrap());


}
