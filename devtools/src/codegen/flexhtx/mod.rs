use bimap::BiHashMap;
use minidsp::formats::xml_config::Setting;
use strong_xml::XmlRead;

use super::spec::*;

pub struct Target {}
impl crate::Target for Target {
    fn filename() -> &'static str {
        "flexhtx.rs"
    }

    fn symbols() -> bimap::BiMap<String, usize> {
        symbols()
    }

    fn device() -> Device {
        device()
    }
}

pub(crate) fn input(input: usize) -> Input {
    Input {
        gate: Some(Gate {
            enable: format!("BM_DGain_{}_status", input + 1),
            gain: Some(format!("BM_DGain_{}", input + 1)),
        }),
        meter: Some(format!("Meter_In_{}", input + 1)),
        //meter_d: Some(format!("Meter_D_In_{}", input + 1)),
        peq: (1..=10usize)
            .rev()
            .map(|index| format!("PEQ_{}_{}", input + 1, index))
            .collect(),
        routing: (0..8usize)
            .map(|output| Gate {
                enable: format!("BM_Mixer_{}_{}_status", input + 1, output + 1),
                gain: Some(format!("BM_Mixer_{}_{}", input + 1, output + 1)),
            })
            .collect(),
    }
}

pub(crate) fn output(output: usize) -> Output {
    let ch = 9 + output;

    Output {
        gate: Gate {
            enable: format!("DGain_{}_0_status", ch),
            gain: Some(format!("DGain_{}_0", ch)),
        },
        meter: Some(format!("Meter_Out_{}", ch)),
        delay_addr: Some(format!("Delay_{}_0", ch)),
        invert_addr: format!("polarity_out_{}_0", ch),
        peq: vec![],
        xover: Some(Crossover {
            peqs: [1, 5]
                .iter()
                .map(|group| format!("BPF_{}_{}", ch, group))
                .chain(
                    [1, 5]
                        .iter()
                        .map(|group| format!("BM_BPF_{}_{}", output + 1, group)),
                )
                .collect(),
        }),
        compressor: Some(Compressor {
            bypass: format!("COMP_{}_0_status", ch),
            threshold: format!("COMP_{}_0_threshold", ch),
            ratio: format!("COMP_{}_0_ratio", ch),
            attack: format!("COMP_{}_0_atime", ch),
            release: format!("COMP_{}_0_rtime", ch),
            meter: Some(format!("Meter_Comp_{}", ch)),
        }),
        fir: None,
    }
}

pub fn device() -> Device {
    Device {
        product_name: "FlexHtx".into(),
        sources: vec![
            "Analog".into(),
            "Toslink".into(),
            "Spdif".into(),
            "Usb".into(),
            "Hdmi".into(),
        ],
        inputs: (0..8).map(input).collect(),
        outputs: (0..8).map(output).collect(),
        fir_max_taps: 0,
        internal_sampling_rate: 48000,
        ..Default::default()
    }
}

pub fn symbols() -> BiHashMap<String, usize> {
    let cfg = include_str!("config.xml");
    Setting::from_str(cfg).unwrap().name_map()
}

#[cfg(test)]
#[test]
fn test_codegen() {
    let mut symbol_map = symbols();
    let spec = device();
    super::generate_static_config(&mut symbol_map, &spec).to_string();
}
