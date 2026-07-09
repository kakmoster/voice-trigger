import esphome.codegen as cg
import esphome.config_validation as cv
from esphome import automation
from esphome.components import microphone, udp
from esphome.const import CONF_ID, CONF_MICROPHONE, CONF_PORT, CONF_ADDRESS

DEPENDENCIES = ["microphone", "udp", "network"]
AUTO_LOAD = ["socket"]

udp_mic_stream_ns = cg.esphome_ns.namespace("udp_mic_stream")
UDPMicStream = udp_mic_stream_ns.class_("UDPMicStream", cg.Component)

CONF_UDP_ID = "udp_id"
CONF_TARGET_HOST = "target_host"
CONF_TARGET_PORT = "target_port"
CONF_SAMPLE_RATE = "sample_rate"
CONF_CHANNELS = "channels"
CONF_BITS_PER_SAMPLE = "bits_per_sample"
CONF_PACKET_SIZE = "packet_size"

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(UDPMicStream),
        cv.Required(CONF_MICROPHONE): cv.use_id(microphone.Microphone),
        cv.Required(CONF_UDP_ID): cv.use_id(udp.UDPComponent),
        cv.Required(CONF_TARGET_HOST): cv.string_strict,
        cv.Optional(CONF_TARGET_PORT, default=5000): cv.port,
        cv.Optional(CONF_SAMPLE_RATE, default=16000): cv.int_range(min=8000, max=48000),
        cv.Optional(CONF_CHANNELS, default=1): cv.one_of(1, 2, int=True),
        cv.Optional(CONF_BITS_PER_SAMPLE, default=16): cv.one_of(16, 32, int=True),
        cv.Optional(CONF_PACKET_SIZE, default=1600): cv.int_range(min=160, max=8192),
    }
).extend(cv.COMPONENT_SCHEMA)

# Actions to start / stop streaming from YAML automations.
StartStreamAction = udp_mic_stream_ns.class_("StartStreamAction", automation.Action)
StopStreamAction = udp_mic_stream_ns.class_("StopStreamAction", automation.Action)


@automation.register_action("udp_mic_stream.start", StartStreamAction, cv.Schema({cv.GenerateID(): cv.use_id(UDPMicStream)}))
async def udp_mic_stream_start_to_code(config, action_id, template_arg, args):
    var = cg.new_Pvariable(action_id, template_arg)
    await cg.register_parented(var, config[CONF_ID])
    return var


@automation.register_action("udp_mic_stream.stop", StopStreamAction, cv.Schema({cv.GenerateID(): cv.use_id(UDPMicStream)}))
async def udp_mic_stream_stop_to_code(config, action_id, template_arg, args):
    var = cg.new_Pvariable(action_id, template_arg)
    await cg.register_parented(var, config[CONF_ID])
    return var


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)

    mic = await cg.get_variable(config[CONF_MICROPHONE])
    cg.add(var.set_microphone(mic))

    udp_comp = await cg.get_variable(config[CONF_UDP_ID])
    cg.add(var.set_udp_id(udp_comp))

    cg.add(var.set_target_host(config[CONF_TARGET_HOST]))
    cg.add(var.set_target_port(config[CONF_TARGET_PORT]))
    cg.add(var.set_sample_rate(config[CONF_SAMPLE_RATE]))
    cg.add(var.set_channels(config[CONF_CHANNELS]))
    cg.add(var.set_bits_per_sample(config[CONF_BITS_PER_SAMPLE]))
    cg.add(var.set_packet_size(config[CONF_PACKET_SIZE]))
