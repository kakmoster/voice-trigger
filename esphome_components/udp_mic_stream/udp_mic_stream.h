#pragma once

#include "esphome/core/component.h"
#include "esphome/core/hal.h"
#include "esphome/components/microphone/microphone.h"
#include "esphome/components/udp/udp.h"
#include "esphome/components/socket/socket.h"
#include <vector>

namespace esphome {
namespace udp_mic_stream {

class UDPMicStream : public Component {
 public:
  void setup() override;
  void loop() override;
  void dump_config() override;

  void set_microphone(microphone::Microphone *mic) { this->mic_ = mic; }
  void set_udp_id(udp::UDPComponent *udp) { this->udp_ = udp; }
  void set_target_host(const std::string &host) { this->target_host_ = host; }
  void set_target_port(uint16_t port) { this->target_port_ = port; }
  void set_sample_rate(uint32_t rate) { this->target_rate_ = rate; }
  void set_channels(uint8_t ch) { this->target_channels_ = ch; }
  void set_bits_per_sample(uint8_t bits) { this->target_bits_ = bits; }
  void set_packet_size(uint32_t size) { this->packet_size_ = size; }

  // Called from YAML actions / switch
  void start_stream();
  void stop_stream();
  bool is_streaming() const { return this->streaming_; }

 protected:
  microphone::Microphone *mic_ = nullptr;
  udp::UDPComponent *udp_ = nullptr;
  std::string target_host_;
  uint16_t target_port_ = 5000;
  uint32_t target_rate_ = 16000;
  uint8_t target_channels_ = 1;
  uint8_t target_bits_ = 16;
  uint32_t packet_size_ = 1600;  // ~100 ms @ 16 kHz / 16-bit

  bool streaming_ = false;

  // Resampling state (simple linear interpolation, 48k -> 16k)
  std::vector<int32_t> resample_buffer_;
  size_t resample_pos_ = 0;
  float resample_ratio_ = 1.0f;

  // Output accumulation buffer (already converted to target format)
  std::vector<uint8_t> out_buffer_;

  void on_mic_data_(const std::vector<uint8_t> &data);
  void flush_packet_();
  void send_udp_(const uint8_t *data, size_t len);
};

}  // namespace udp_mic_stream
}  // namespace esphome
